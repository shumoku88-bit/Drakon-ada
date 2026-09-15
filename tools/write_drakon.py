#!/usr/bin/env python3
"""Render an O3a DRAKON projection as a DRAKON Editor SQLite document."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3
import sys

INPUT_SCHEMA = "drakon-ada/drakon-projection/v1"
MAP_SCHEMA = "drakon-ada/drn-projection-map/v1"
BASE_X, BASE_Y = 240, 100
BRANCH_SPACING, RANK_SPACING = 260, 120
MERGE_MARGIN, LOOP_RETURN_MARGIN, RETURN_GAP = 20, 20, 130
ICON_SIZE = {"beginend": (100, 20), "action": (100, 20), "if": (60, 20)}
ROLES = {"next", "true", "false", "loop_body", "loop_exit", "back", "return"}


class WriterError(ValueError):
    pass


def _edge(outgoing, node_id, role):
    found = [e for e in outgoing[node_id] if e["role"] == role]
    if len(found) != 1:
        raise WriterError(f"{node_id}: expected exactly one {role} edge")
    return found[0]


def _validate(projection):
    if projection.get("schema") != INPUT_SCHEMA:
        raise WriterError(f"unsupported projection schema: {projection.get('schema')!r}")
    nodes, edges = projection.get("nodes"), projection.get("edges")
    if not isinstance(nodes, list) or not nodes:
        raise WriterError("projection nodes must be a non-empty list")
    if not isinstance(edges, list):
        raise WriterError("projection edges must be a list")
    layout = projection.get("layout")
    if not isinstance(layout, dict):
        raise WriterError("projection layout must be an object")
    if layout.get("detached_nodes", []):
        raise WriterError("O3b cannot write detached nodes into one connected DRAKON diagram")

    by_id, orders = {}, set()
    for node in nodes:
        if not isinstance(node, dict):
            raise WriterError("every projected node must be an object")
        node_id, icon = node.get("id"), node.get("icon")
        semantic, order = node.get("semantic_kind"), node.get("order")
        nl = node.get("layout")
        if not isinstance(node_id, str) or not node_id or node_id in by_id:
            raise WriterError(f"invalid or duplicate projected node id: {node_id!r}")
        if icon not in ICON_SIZE:
            raise WriterError(f"{node_id}: unsupported DRAKON icon {icon!r}")
        if semantic not in {"entry", "exit", "action", "decision", "loop", "return"}:
            raise WriterError(f"{node_id}: unsupported semantic kind {semantic!r}")
        if not isinstance(node.get("text"), str) or not node["text"].strip():
            raise WriterError(f"{node_id}: projected node text must be non-empty")
        if not isinstance(order, int) or order < 0 or order in orders:
            raise WriterError(f"{node_id}: order must be a unique non-negative integer")
        if not isinstance(nl, dict) or nl.get("reachable") is not True:
            raise WriterError(f"{node_id}: O3b only accepts reachable projected nodes")
        if not isinstance(nl.get("rank"), int) or nl["rank"] < 0:
            raise WriterError(f"{node_id}: layout rank must be a non-negative integer")
        by_id[node_id] = node
        orders.add(order)

    entry, exit_id = projection.get("entry_node"), projection.get("exit_node")
    if entry not in by_id or by_id[entry]["semantic_kind"] != "entry":
        raise WriterError("entry_node must reference the projected entry")
    if exit_id not in by_id or by_id[exit_id]["semantic_kind"] != "exit":
        raise WriterError("exit_node must reference the projected exit")

    outgoing, seen = defaultdict(list), set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise WriterError("every projected edge must be an object")
        source, target, role = edge.get("from"), edge.get("to"), edge.get("role")
        if source not in by_id or target not in by_id:
            raise WriterError(f"dangling projected edge: {source!r}->{target!r}")
        if role not in ROLES:
            raise WriterError(f"{source}->{target}: unsupported projected role {role!r}")
        key = (source, target, role)
        if key in seen:
            raise WriterError(f"duplicate projected edge: {source}->{target} ({role})")
        seen.add(key)
        outgoing[source].append(edge)

    for node in nodes:
        node_id, kind = node["id"], node["semantic_kind"]
        outs, roles = outgoing[node_id], [e["role"] for e in outgoing[node_id]]
        if kind == "entry" and roles != ["next"]:
            raise WriterError(f"{node_id}: entry must have exactly one next edge")
        if kind == "exit" and roles:
            raise WriterError(f"{node_id}: exit must not have outgoing edges")
        if kind == "decision" and sorted(roles) != ["false", "true"]:
            raise WriterError(f"{node_id}: decision must have exactly one true and one false edge")
        if kind == "loop" and sorted(roles) != ["loop_body", "loop_exit"]:
            raise WriterError(f"{node_id}: loop must have exactly one loop_body and one loop_exit edge")
        if kind == "return" and (len(outs) != 1 or roles != ["return"] or outs[0]["to"] != exit_id):
            raise WriterError(f"{node_id}: return must have exactly one return edge to exit")
        if kind == "action" and (len(outs) != 1 or roles[0] not in {"next", "back"}):
            raise WriterError(f"{node_id}: action must have exactly one next or back edge")
    return sorted(nodes, key=lambda n: n["order"]), edges, by_id, outgoing


def _ranks(nodes, edges, by_id, outgoing):
    rank = {n["id"]: int(n["layout"]["rank"]) for n in nodes}
    for edge in edges:
        if edge["role"] == "back":
            loop_id = edge["to"]
            if by_id[loop_id]["semantic_kind"] != "loop":
                raise WriterError(f"{edge['from']}->{loop_id}: back edge must target a loop")
            after = _edge(outgoing, loop_id, "loop_exit")["to"]
            rank[after] = max(rank[after], rank[edge["from"]] + 1)
    forward = [e for e in edges if e["role"] != "back"]
    for _ in range(max(1, len(nodes) ** 2)):
        changed = False
        for edge in forward:
            wanted = rank[edge["from"]] + 1
            if rank[edge["to"]] < wanted:
                rank[edge["to"]] = wanted
                changed = True
        if not changed:
            return rank
    raise WriterError("physical rank constraints did not converge")


def _reachable(start, adjacency):
    seen, todo = set(), [start]
    while todo:
        node_id = todo.pop()
        if node_id not in seen:
            seen.add(node_id)
            todo.extend(adjacency[node_id])
    return seen


def _regions(nodes, edges, by_id, outgoing, rank):
    order = {n["id"]: n["order"] for n in nodes}
    adjacency = defaultdict(list)
    for edge in edges:
        if edge["role"] != "back":
            adjacency[edge["from"]].append(edge["to"])

    regions = []
    for node in nodes:
        source, kind = node["id"], node["semantic_kind"]
        if kind not in {"decision", "loop"}:
            continue
        if kind == "decision":
            target = _edge(outgoing, source, "true")["to"]
            other = _edge(outgoing, source, "false")["to"]
            common = _reachable(target, adjacency) & _reachable(other, adjacency)
            if not common:
                raise WriterError(f"{source}: decision paths have no forward merge")
            end = min(common, key=lambda n: (rank[n], order[n]))
            role = "true"
        else:
            target = _edge(outgoing, source, "loop_body")["to"]
            end = _edge(outgoing, source, "loop_exit")["to"]
            role = "loop_body"

        body, todo = set(), [target]
        while todo:
            node_id = todo.pop()
            if node_id == end or node_id in body:
                continue
            body.add(node_id)
            if by_id[node_id]["semantic_kind"] in {"decision", "loop"}:
                raise WriterError(f"{source}: nested branch source {node_id} is outside the initial O3b slice")
            todo.extend(e["to"] for e in outgoing[node_id] if e["role"] != "back")
        if not body:
            raise WriterError(f"{source}: branch body is empty in the initial O3b slice")
        if rank[end] <= rank[source]:
            raise WriterError(f"{source}: branch merge must be below branch source")
        regions.append({"source": source, "role": role, "target": target, "end": end,
                        "body": body, "start": rank[source], "finish": rank[end],
                        "order": order[source]})

    occupied = defaultdict(list)
    for region in sorted(regions, key=lambda r: (-r["start"], -r["order"])):
        interval, lane = (region["start"], region["finish"]), 1
        while any(max(interval[0], u[0]) < min(interval[1], u[1]) for u in occupied[lane]):
            lane += 1
        occupied[lane].append(interval)
        region["lane"] = lane

    lane_of = {n["id"]: 0 for n in nodes}
    for region in regions:
        if lane_of[region["source"]] or lane_of[region["end"]]:
            raise WriterError(f"{region['source']}: branch source or merge inside another branch is unsupported")
        for node_id in region["body"]:
            if lane_of[node_id]:
                raise WriterError(f"{node_id}: projected branch regions overlap")
            lane_of[node_id] = region["lane"]
    return regions, lane_of


def _merge(intervals):
    values = sorted((min(a, b), max(a, b)) for a, b in intervals if a != b)
    out = []
    for start, end in values:
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def _ranges_touch(a1, a2, b1, b2):
    left1, right1 = sorted((a1, a2))
    left2, right2 = sorted((b1, b2))
    return max(left1, left2) <= min(right1, right2)


def _check_route_separation(horizontals, arrows):
    for y, intervals in horizontals.items():
        normalized = [(min(a, b), max(a, b)) for a, b in intervals if a != b]
        for index, first in enumerate(normalized):
            for second in normalized[index + 1:]:
                if _ranges_touch(first[0], first[1], second[0], second[1]):
                    raise WriterError(
                        f"horizontal routes share corridor y={y}: {first} and {second}"
                    )

        for start, end in normalized:
            for arrow in arrows:
                top = (arrow["x"] - arrow["w"], arrow["x"])
                bottom = (arrow["x"] - arrow["a"], arrow["x"])
                for arrow_y, segment in (
                    (arrow["y"], top),
                    (arrow["y"] + arrow["h"], bottom),
                ):
                    if y == arrow_y and _ranges_touch(
                        start, end, segment[0], segment[1]
                    ):
                        raise WriterError(
                            "branch merge and loop return share a horizontal corridor"
                        )

def _schema(db):
    db.executescript("""
    CREATE TABLE info(key TEXT PRIMARY KEY,value TEXT);
    CREATE TABLE diagrams(diagram_id INTEGER PRIMARY KEY,name TEXT UNIQUE,origin TEXT,description TEXT,zoom DOUBLE);
    CREATE TABLE state(row INTEGER PRIMARY KEY,current_dia INTEGER,description TEXT);
    CREATE TABLE items(item_id INTEGER PRIMARY KEY,diagram_id INTEGER,type TEXT,text TEXT,selected INTEGER,x INTEGER,y INTEGER,w INTEGER,h INTEGER,a INTEGER,b INTEGER,aux_value INTEGER,color TEXT,format TEXT,text2 TEXT);
    CREATE TABLE diagram_info(diagram_id INTEGER,name TEXT,value TEXT,PRIMARY KEY(diagram_id,name));
    CREATE TABLE tree_nodes(node_id INTEGER PRIMARY KEY,parent INTEGER,type TEXT,name TEXT,diagram_id INTEGER);
    CREATE INDEX items_per_diagram ON items(diagram_id);
    CREATE UNIQUE INDEX node_for_diagram ON tree_nodes(diagram_id);
    """)


def _item(db, item_id, item_type, text="", *, x, y, w, h, a=0, b=0):
    db.execute("INSERT INTO items(item_id,diagram_id,type,text,selected,x,y,w,h,a,b) VALUES(?,1,?,?,0,?,?,?,?,?,?)",
               (item_id, item_type, text, x, y, w, h, a, b))


def write_projection(projection, output: Path):
    nodes, edges, by_id, outgoing = _validate(projection)
    if output.exists():
        output.unlink()
    rank = _ranks(nodes, edges, by_id, outgoing)
    regions, lane_of = _regions(nodes, edges, by_id, outgoing, rank)
    region_for = {r["source"]: r for r in regions}
    geo = {}
    for node in nodes:
        lane = lane_of[node["id"]]
        w, h = ICON_SIZE[node["icon"]]
        geo[node["id"]] = {"x": BASE_X + lane * BRANCH_SPACING,
                           "y": BASE_Y + rank[node["id"]] * RANK_SPACING,
                           "w": w, "h": h, "lane": lane, "rank": rank[node["id"]]}

    verticals, horizontals, arrows = defaultdict(list), defaultdict(list), []
    def v(x, a, b):
        if a != b: verticals[x].append((a, b))
    def h(y, a, b):
        if a != b: horizontals[y].append((a, b))

    for edge in edges:
        source, target, role = edge["from"], edge["to"], edge["role"]
        sg, tg = geo[source], geo[target]
        if role == "back":
            if by_id[target]["semantic_kind"] != "loop":
                raise WriterError(f"{source}->{target}: back edge must target a loop")
            region = region_for.get(target)
            branch_x = BASE_X + region["lane"] * BRANCH_SPACING if region else None
            if branch_x is None or sg["x"] != branch_x or by_id[source]["icon"] != "action":
                raise WriterError(f"{source}->{target}: invalid loop return source")
            corridor = branch_x + RETURN_GAP
            bottom = sg["y"] + sg["h"] + LOOP_RETURN_MARGIN
            top = tg["y"] - RANK_SPACING // 2
            top_width, bottom_width = corridor - tg["x"], corridor - branch_x
            if min(top_width, bottom_width) < 30 or top >= tg["y"] - tg["h"]:
                raise WriterError(f"{target}: no room for DRAKON return arrow")
            v(branch_x, sg["y"] + sg["h"], bottom)
            arrows.append({"x": corridor, "y": top, "w": top_width,
                           "h": bottom - top, "a": bottom_width, "b": 0})
            continue
        if role in {"true", "loop_body"}:
            region = region_for.get(source)
            if not region or region["role"] != role:
                raise WriterError(f"{source}: branch region does not match {role}")
            branch_x = BASE_X + region["lane"] * BRANCH_SPACING
            if tg["x"] != branch_x:
                raise WriterError(f"{source}->{target}: branch target is on wrong lane")
            v(branch_x, sg["y"], tg["y"] - tg["h"])
            continue

        source_bottom, target_top = sg["y"] + sg["h"], tg["y"] - tg["h"]
        if sg["x"] == tg["x"]:
            if target_top <= source_bottom:
                raise WriterError(f"{source}->{target}: forward icons overlap vertically")
            v(sg["x"], source_bottom, target_top)
        else:
            if tg["lane"] != 0:
                raise WriterError(f"{source}->{target}: cross-lane forward merge must target main lane")
            join = target_top - MERGE_MARGIN
            if join <= source_bottom:
                raise WriterError(f"{source}->{target}: no room for cross-lane merge")
            v(sg["x"], source_bottom, join)
            h(join, sg["x"], tg["x"])
            v(tg["x"], join, target_top)

    _check_route_separation(horizontals, arrows)

    icon_rows, node_to_item, item_id = [], {}, 1
    for node in nodes:
        g, arm = geo[node["id"]], 0
        if node["icon"] == "if":
            region = region_for.get(node["id"])
            if not region:
                raise WriterError(f"{node['id']}: if icon has no branch region")
            arm = BASE_X + region["lane"] * BRANCH_SPACING - (g["x"] + g["w"])
            if arm < 20:
                raise WriterError(f"{node['id']}: DRAKON if branch arm is too short")
        icon_rows.append((item_id, node["icon"], node["text"], g["x"], g["y"], g["w"], g["h"], arm, 0))
        node_to_item[node["id"]] = item_id
        item_id += 1

    line_rows = []
    for x in sorted(verticals):
        for y1, y2 in _merge(verticals[x]):
            line_rows.append((item_id, "vertical", "", x, y1, 0, y2-y1, 0, 0)); item_id += 1
    for y in sorted(horizontals):
        for x1, x2 in _merge(horizontals[y]):
            line_rows.append((item_id, "horizontal", "", x1, y, x2-x1, 0, 0, 0)); item_id += 1
    for arrow in arrows:
        line_rows.append((item_id, "arrow", "", arrow["x"], arrow["y"], arrow["w"], arrow["h"], arrow["a"], 0)); item_id += 1

    subprogram = projection.get("subprogram")
    if not isinstance(subprogram, dict) or not isinstance(subprogram.get("name"), str) or not subprogram["name"].strip():
        raise WriterError("projection subprogram name must be non-empty")
    mapping = {"schema": MAP_SCHEMA, "projection_schema": INPUT_SCHEMA,
               "source": projection.get("source"), "subprogram": subprogram,
               "entry_node": projection.get("entry_node"), "exit_node": projection.get("exit_node"),
               "nodes": [{"node_id": n["id"], "item_id": node_to_item[n["id"]],
                           "semantic_kind": n["semantic_kind"], "physical": geo[n["id"]],
                           "trace": n.get("trace")} for n in nodes],
               "edges": [{"from": e["from"], "to": e["to"], "role": e["role"],
                           "back": bool(e.get("back", e["role"] == "back"))} for e in edges]}

    with sqlite3.connect(output) as db:
        _schema(db)
        db.executemany("INSERT INTO info(key,value) VALUES(?,?)",
                       [("type","drakon"),("version","2"),("start_version","1"),("language","SPARK")])
        db.execute("INSERT INTO diagrams(diagram_id,name,origin,description,zoom) VALUES(1,?,'0 0',?,100)",
                   (subprogram["name"].strip(), "Derived DRAKON observation; Ada/SPARK source remains authoritative."))
        db.execute("INSERT INTO state(row,current_dia,description) VALUES(1,1,?)",
                   ("Generated by Drakon-ada O3b from normalized projection.",))
        db.execute("INSERT INTO tree_nodes(node_id,parent,type,name,diagram_id) VALUES(1,0,'item',NULL,1)")
        for row in icon_rows + line_rows:
            _item(db, row[0], row[1], row[2], x=row[3], y=row[4], w=row[5], h=row[6], a=row[7], b=row[8])
        db.execute("INSERT INTO diagram_info(diagram_id,name,value) VALUES(1,?,?)",
                   (MAP_SCHEMA, json.dumps(mapping, sort_keys=True, separators=(",",":"), ensure_ascii=False)))
    return mapping


def main():
    parser = argparse.ArgumentParser(description="Write a DRAKON Editor .drn from O3a projection JSON")
    parser.add_argument("projection")
    parser.add_argument("output")
    args = parser.parse_args()
    try:
        with (sys.stdin if args.projection == "-" else Path(args.projection).open(encoding="utf-8")) as stream:
            projection = json.load(stream)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_projection(projection, output)
    except (OSError, sqlite3.Error, json.JSONDecodeError, WriterError) as exc:
        print(f"DRAKON writer error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
