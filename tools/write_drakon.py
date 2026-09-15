#!/usr/bin/env python3
"""Write a DRAKON Editor SQLite document from a normalized DRAKON projection."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any

INPUT_SCHEMA = "drakon-ada/drakon-projection/v1"
MAP_SCHEMA = "drakon-ada/drn-projection-map/v1"

BASE_X = 240
BASE_Y = 100
BRANCH_SPACING = 260
RANK_SPACING = 120
MERGE_GAP = 40
RETURN_GAP = 130

ICON_SIZE = {
    "beginend": (100, 20),
    "action": (100, 20),
    "if": (60, 20),
}
ALLOWED_ROLES = {
    "next",
    "true",
    "false",
    "loop_body",
    "loop_exit",
    "back",
    "return",
}


class WriterError(ValueError):
    """Raised when a projection cannot be represented safely in O3b."""


def _require_object(value: Any, message: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WriterError(message)
    return value


def _validate_projection(
    projection: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if projection.get("schema") != INPUT_SCHEMA:
        raise WriterError(f"unsupported projection schema: {projection.get('schema')!r}")

    nodes = projection.get("nodes")
    edges = projection.get("edges")
    if not isinstance(nodes, list) or not nodes:
        raise WriterError("projection nodes must be a non-empty list")
    if not isinstance(edges, list):
        raise WriterError("projection edges must be a list")

    layout = _require_object(projection.get("layout"), "projection layout must be an object")
    detached = layout.get("detached_nodes", [])
    if detached:
        raise WriterError(
            "O3b cannot write detached nodes into one connected DRAKON diagram"
        )

    by_id: dict[str, dict[str, Any]] = {}
    orders: set[int] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise WriterError("every projected node must be an object")
        node_id = node.get("id")
        icon = node.get("icon")
        semantic = node.get("semantic_kind")
        text = node.get("text")
        order = node.get("order")
        node_layout = node.get("layout")
        if not isinstance(node_id, str) or not node_id:
            raise WriterError("every projected node must have a non-empty string id")
        if node_id in by_id:
            raise WriterError(f"duplicate projected node id: {node_id}")
        if icon not in ICON_SIZE:
            raise WriterError(f"{node_id}: unsupported DRAKON icon {icon!r}")
        if semantic not in {"entry", "exit", "action", "decision", "loop", "return"}:
            raise WriterError(f"{node_id}: unsupported semantic kind {semantic!r}")
        if not isinstance(text, str) or not text.strip():
            raise WriterError(f"{node_id}: projected node text must be non-empty")
        if not isinstance(order, int) or order < 0 or order in orders:
            raise WriterError(f"{node_id}: order must be a unique non-negative integer")
        orders.add(order)
        if not isinstance(node_layout, dict):
            raise WriterError(f"{node_id}: layout must be an object")
        if node_layout.get("reachable") is not True:
            raise WriterError(f"{node_id}: O3b only accepts reachable projected nodes")
        if not isinstance(node_layout.get("rank"), int) or node_layout["rank"] < 0:
            raise WriterError(f"{node_id}: layout rank must be a non-negative integer")
        by_id[node_id] = node

    entry = projection.get("entry_node")
    exit_node = projection.get("exit_node")
    if entry not in by_id or by_id[entry]["semantic_kind"] != "entry":
        raise WriterError("entry_node must reference the projected entry")
    if exit_node not in by_id or by_id[exit_node]["semantic_kind"] != "exit":
        raise WriterError("exit_node must reference the projected exit")

    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_edges: set[tuple[str, str, str]] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise WriterError("every projected edge must be an object")
        source = edge.get("from")
        target = edge.get("to")
        role = edge.get("role")
        if source not in by_id or target not in by_id:
            raise WriterError(f"dangling projected edge: {source!r}->{target!r}")
        if role not in ALLOWED_ROLES:
            raise WriterError(f"{source}->{target}: unsupported projected role {role!r}")
        key = (source, target, role)
        if key in seen_edges:
            raise WriterError(f"duplicate projected edge: {source}->{target} ({role})")
        seen_edges.add(key)
        outgoing[source].append(edge)

    for node in nodes:
        node_id = node["id"]
        semantic = node["semantic_kind"]
        roles = [edge["role"] for edge in outgoing[node_id]]
        if semantic == "entry" and roles != ["next"]:
            raise WriterError(f"{node_id}: entry must have exactly one next edge")
        if semantic == "exit" and roles:
            raise WriterError(f"{node_id}: exit must not have outgoing edges")
        if semantic == "decision" and sorted(roles) != ["false", "true"]:
            raise WriterError(
                f"{node_id}: decision must have exactly one true and one false edge"
            )
        if semantic == "loop" and sorted(roles) != ["loop_body", "loop_exit"]:
            raise WriterError(
                f"{node_id}: loop must have exactly one loop_body and one loop_exit edge"
            )
        if semantic == "return":
            if len(outgoing[node_id]) != 1 or roles != ["return"]:
                raise WriterError(f"{node_id}: return must have exactly one return edge")
            if outgoing[node_id][0]["to"] != exit_node:
                raise WriterError(f"{node_id}: return must target the projected exit")
        if semantic == "action":
            if len(outgoing[node_id]) != 1 or roles[0] not in {"next", "back"}:
                raise WriterError(
                    f"{node_id}: action must have exactly one next or back edge"
                )

    return sorted(nodes, key=lambda node: node["order"]), edges, by_id


def _edge_by_role(
    outgoing: dict[str, list[dict[str, Any]]], node_id: str, role: str
) -> dict[str, Any]:
    matches = [edge for edge in outgoing[node_id] if edge["role"] == role]
    if len(matches) != 1:
        raise WriterError(f"{node_id}: expected exactly one {role} edge")
    return matches[0]


def _compute_physical_ranks(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> dict[str, int]:
    ranks = {node["id"]: int(node["layout"]["rank"]) for node in nodes}
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        outgoing[edge["from"]].append(edge)

    # A loop continuation must be drawn below the complete loop body. O3a ranks
    # are semantic layout hints; this is a renderer-only spacing constraint.
    for edge in edges:
        if edge["role"] != "back":
            continue
        loop_id = edge["to"]
        if by_id[loop_id]["semantic_kind"] != "loop":
            raise WriterError(f"{edge['from']}->{loop_id}: back edge must target a loop")
        exit_target = _edge_by_role(outgoing, loop_id, "loop_exit")["to"]
        ranks[exit_target] = max(ranks[exit_target], ranks[edge["from"]] + 1)

    forward = [edge for edge in edges if edge["role"] != "back"]
    limit = max(1, len(nodes) * len(nodes))
    for _ in range(limit):
        changed = False
        for edge in forward:
            wanted = ranks[edge["from"]] + 1
            if ranks[edge["to"]] < wanted:
                ranks[edge["to"]] = wanted
                changed = True
        if not changed:
            return ranks
    raise WriterError("physical rank constraints did not converge")


def _forward_reachable(
    start: str,
    adjacency: dict[str, list[str]],
) -> set[str]:
    seen: set[str] = set()
    pending = [start]
    while pending:
        node_id = pending.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        pending.extend(adjacency[node_id])
    return seen


def _branch_regions(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    ranks: dict[str, int],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    order = {node["id"]: node["order"] for node in nodes}
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        outgoing[edge["from"]].append(edge)
        if edge["role"] != "back":
            adjacency[edge["from"]].append(edge["to"])

    regions: list[dict[str, Any]] = []
    for node in nodes:
        source = node["id"]
        semantic = node["semantic_kind"]
        if semantic not in {"decision", "loop"}:
            continue

        if semantic == "decision":
            branch_target = _edge_by_role(outgoing, source, "true")["to"]
            alternate = _edge_by_role(outgoing, source, "false")["to"]
            common = _forward_reachable(branch_target, adjacency) & _forward_reachable(
                alternate, adjacency
            )
            if not common:
                raise WriterError(f"{source}: decision paths have no forward merge")
            end = min(common, key=lambda node_id: (ranks[node_id], order[node_id]))
            role = "true"
        else:
            branch_target = _edge_by_role(outgoing, source, "loop_body")["to"]
            end = _edge_by_role(outgoing, source, "loop_exit")["to"]
            role = "loop_body"

        body: set[str] = set()
        pending = [branch_target]
        while pending:
            node_id = pending.pop()
            if node_id == end or node_id in body:
                continue
            body.add(node_id)
            member = by_id[node_id]
            if member["semantic_kind"] in {"decision", "loop"}:
                raise WriterError(
                    f"{source}: nested branch source {node_id} is outside the initial O3b slice"
                )
            for edge in outgoing[node_id]:
                if edge["role"] != "back":
                    pending.append(edge["to"])

        if not body:
            raise WriterError(f"{source}: branch body is empty in the initial O3b slice")
        start_rank = ranks[source]
        end_rank = ranks[end]
        if end_rank <= start_rank:
            raise WriterError(f"{source}: branch merge must be below branch source")
        regions.append(
            {
                "source": source,
                "role": role,
                "target": branch_target,
                "end": end,
                "body": body,
                "start_rank": start_rank,
                "end_rank": end_rank,
                "order": order[source],
            }
        )

    # Allocate inner/later branches first. Half-open intervals let a lane be
    # reused exactly at a merge rank.
    occupancy: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for region in sorted(
        regions, key=lambda item: (-item["start_rank"], -item["order"])
    ):
        lane = 1
        interval = (region["start_rank"], region["end_rank"])
        while True:
            conflict = any(
                max(interval[0], used[0]) < min(interval[1], used[1])
                for used in occupancy[lane]
            )
            if not conflict:
                break
            lane += 1
        occupancy[lane].append(interval)
        region["lane"] = lane

    node_lane = {node["id"]: 0 for node in nodes}
    for region in regions:
        if node_lane[region["source"]] != 0:
            raise WriterError(
                f"{region['source']}: branch source inside another branch is unsupported"
            )
        if node_lane[region["end"]] != 0:
            raise WriterError(
                f"{region['source']}: merge inside another branch is unsupported"
            )
        for node_id in region["body"]:
            if node_lane[node_id] != 0:
                raise WriterError(f"{node_id}: projected branch regions overlap")
            node_lane[node_id] = region["lane"]

    return regions, node_lane


def _merge_intervals(
    intervals: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    normalized = sorted((min(a, b), max(a, b)) for a, b in intervals if a != b)
    if not normalized:
        return []
    result = [normalized[0]]
    for start, end in normalized[1:]:
        old_start, old_end = result[-1]
        if start <= old_end:
            result[-1] = (old_start, max(old_end, end))
        else:
            result.append((start, end))
    return result


def _create_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE info (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE diagrams (
            diagram_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            origin TEXT,
            description TEXT,
            zoom DOUBLE
        );
        CREATE TABLE state (
            row INTEGER PRIMARY KEY,
            current_dia INTEGER,
            description TEXT
        );
        CREATE TABLE items (
            item_id INTEGER PRIMARY KEY,
            diagram_id INTEGER,
            type TEXT,
            text TEXT,
            selected INTEGER,
            x INTEGER,
            y INTEGER,
            w INTEGER,
            h INTEGER,
            a INTEGER,
            b INTEGER,
            aux_value INTEGER,
            color TEXT,
            format TEXT,
            text2 TEXT
        );
        CREATE TABLE diagram_info (
            diagram_id INTEGER,
            name TEXT,
            value TEXT,
            PRIMARY KEY (diagram_id, name)
        );
        CREATE TABLE tree_nodes (
            node_id INTEGER PRIMARY KEY,
            parent INTEGER,
            type TEXT,
            name TEXT,
            diagram_id INTEGER
        );
        CREATE INDEX items_per_diagram ON items(diagram_id);
        CREATE UNIQUE INDEX node_for_diagram ON tree_nodes(diagram_id);
        """
    )


def _insert_item(
    db: sqlite3.Connection,
    item_id: int,
    item_type: str,
    *,
    text: str = "",
    x: int,
    y: int,
    w: int,
    h: int,
    a: int = 0,
    b: int = 0,
) -> None:
    db.execute(
        """
        INSERT INTO items
          (item_id, diagram_id, type, text, selected, x, y, w, h, a, b)
        VALUES (?, 1, ?, ?, 0, ?, ?, ?, ?, ?, ?)
        """,
        (item_id, item_type, text, x, y, w, h, a, b),
    )


def write_projection(projection: dict[str, Any], output: Path) -> dict[str, Any]:
    nodes, edges, by_id = _validate_projection(projection)
    if output.exists():
        output.unlink()

    ranks = _compute_physical_ranks(nodes, edges, by_id)
    regions, node_lane = _branch_regions(nodes, edges, by_id, ranks)
    region_by_source = {region["source"]: region for region in regions}

    geometry: dict[str, dict[str, int]] = {}
    for node in nodes:
        node_id = node["id"]
        lane = node_lane[node_id]
        x = BASE_X + lane * BRANCH_SPACING
        y = BASE_Y + ranks[node_id] * RANK_SPACING
        w, h = ICON_SIZE[node["icon"]]
        geometry[node_id] = {
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "lane": lane,
            "rank": ranks[node_id],
        }

    verticals: dict[int, list[tuple[int, int]]] = defaultdict(list)
    horizontals: dict[int, list[tuple[int, int]]] = defaultdict(list)
    arrows: list[dict[str, int]] = []

    def add_vertical(x: int, y1: int, y2: int) -> None:
        if y1 != y2:
            verticals[x].append((y1, y2))

    def add_horizontal(y: int, x1: int, x2: int) -> None:
        if x1 != x2:
            horizontals[y].append((x1, x2))

    for edge in edges:
        source = edge["from"]
        target = edge["to"]
        role = edge["role"]
        sg = geometry[source]
        tg = geometry[target]

        if role == "back":
            if by_id[target]["semantic_kind"] != "loop":
                raise WriterError(f"{source}->{target}: back edge must target a loop")
            region = region_by_source.get(target)
            if region is None:
                raise WriterError(f"{target}: loop branch region is missing")
            branch_x = BASE_X + region["lane"] * BRANCH_SPACING
            if sg["x"] != branch_x:
                raise WriterError(
                    f"{source}->{target}: back source must stay on the loop body lane"
                )
            if by_id[source]["icon"] != "action":
                raise WriterError(f"{source}: back source must render as an action icon")
            corridor_x = branch_x + RETURN_GAP
            source_right = sg["x"] + sg["w"]
            bottom_offset = corridor_x - source_right
            if bottom_offset < 30:
                raise WriterError(f"{source}: not enough room for DRAKON return arrow")
            if sg["y"] <= tg["y"]:
                raise WriterError(f"{source}->{target}: back source must be below loop")
            arrows.append(
                {
                    "x": corridor_x,
                    "y": tg["y"],
                    "w": corridor_x - branch_x,
                    "h": sg["y"] - tg["y"],
                    "a": bottom_offset,
                    "b": 0,
                }
            )
            continue

        if role in {"true", "loop_body"}:
            region = region_by_source.get(source)
            if region is None or region["role"] != role:
                raise WriterError(f"{source}: branch region does not match {role}")
            branch_x = BASE_X + region["lane"] * BRANCH_SPACING
            if tg["x"] != branch_x:
                raise WriterError(f"{source}->{target}: branch target is on wrong lane")
            add_vertical(branch_x, sg["y"], tg["y"] - tg["h"])
            continue

        source_bottom = sg["y"] + sg["h"]
        target_top = tg["y"] - tg["h"]
        if sg["x"] == tg["x"]:
            if target_top <= source_bottom:
                raise WriterError(
                    f"{source}->{target}: forward icons overlap vertically"
                )
            add_vertical(sg["x"], source_bottom, target_top)
            continue

        # A branch rejoins a later main continuation. Keep the horizontal join
        # below branch-local work and slightly above the merge icon.
        if tg["lane"] != 0:
            raise WriterError(
                f"{source}->{target}: cross-lane forward merge must target main lane"
            )
        merge_y = target_top - MERGE_GAP
        if merge_y <= source_bottom:
            raise WriterError(f"{source}->{target}: no room for cross-lane merge")
        add_vertical(sg["x"], source_bottom, merge_y)
        add_horizontal(merge_y, sg["x"], tg["x"])
        add_vertical(tg["x"], merge_y, target_top)

    # Ensure every if icon exposes the right-hand YES/body arm exactly to its
    # allocated branch lane. That arm is intrinsic to DRAKON Editor's if item.
    icon_rows: list[dict[str, Any]] = []
    node_to_item: dict[str, int] = {}
    item_id = 1
    for node in nodes:
        node_id = node["id"]
        g = geometry[node_id]
        a = 0
        b = 0
        if node["icon"] == "if":
            region = region_by_source.get(node_id)
            if region is None:
                raise WriterError(f"{node_id}: if icon has no branch region")
            branch_x = BASE_X + region["lane"] * BRANCH_SPACING
            a = branch_x - (g["x"] + g["w"])
            if a < 20:
                raise WriterError(f"{node_id}: DRAKON if branch arm is too short")
        icon_rows.append(
            {
                "item_id": item_id,
                "item_type": node["icon"],
                "text": node["text"],
                "x": g["x"],
                "y": g["y"],
                "w": g["w"],
                "h": g["h"],
                "a": a,
                "b": b,
            }
        )
        node_to_item[node_id] = item_id
        item_id += 1

    line_rows: list[dict[str, Any]] = []
    for x in sorted(verticals):
        for y1, y2 in _merge_intervals(verticals[x]):
            line_rows.append(
                {
                    "item_id": item_id,
                    "item_type": "vertical",
                    "text": "",
                    "x": x,
                    "y": y1,
                    "w": 0,
                    "h": y2 - y1,
                    "a": 0,
                    "b": 0,
                }
            )
            item_id += 1
    for y in sorted(horizontals):
        for x1, x2 in _merge_intervals(horizontals[y]):
            line_rows.append(
                {
                    "item_id": item_id,
                    "item_type": "horizontal",
                    "text": "",
                    "x": x1,
                    "y": y,
                    "w": x2 - x1,
                    "h": 0,
                    "a": 0,
                    "b": 0,
                }
            )
            item_id += 1
    for arrow in arrows:
        line_rows.append(
            {
                "item_id": item_id,
                "item_type": "arrow",
                "text": "",
                **arrow,
            }
        )
        item_id += 1

    subprogram = _require_object(
        projection.get("subprogram"), "projection subprogram must be an object"
    )
    name = subprogram.get("name")
    if not isinstance(name, str) or not name.strip():
        raise WriterError("projection subprogram name must be non-empty")

    mapping = {
        "schema": MAP_SCHEMA,
        "projection_schema": INPUT_SCHEMA,
        "source": projection.get("source"),
        "subprogram": subprogram,
        "entry_node": projection.get("entry_node"),
        "exit_node": projection.get("exit_node"),
        "nodes": [
            {
                "node_id": node["id"],
                "item_id": node_to_item[node["id"]],
                "semantic_kind": node["semantic_kind"],
                "physical": geometry[node["id"]],
                "trace": node.get("trace"),
            }
            for node in nodes
        ],
        "edges": [
            {
                "from": edge["from"],
                "to": edge["to"],
                "role": edge["role"],
                "back": bool(edge.get("back", edge["role"] == "back")),
            }
            for edge in edges
        ],
    }

    with sqlite3.connect(output) as db:
        _create_schema(db)
        db.executemany(
            "INSERT INTO info(key, value) VALUES (?, ?)",
            [
                ("type", "drakon"),
                ("version", "2"),
                ("start_version", "1"),
                ("language", "SPARK"),
            ],
        )
        db.execute(
            """
            INSERT INTO diagrams(diagram_id, name, origin, description, zoom)
            VALUES (1, ?, '0 0', ?, 100)
            """,
            (
                name.strip(),
                "Derived DRAKON observation; Ada/SPARK source remains authoritative.",
            ),
        )
        db.execute(
            "INSERT INTO state(row, current_dia, description) VALUES (1, 1, ?)",
            ("Generated by Drakon-ada O3b from normalized projection.",),
        )
        db.execute(
            """
            INSERT INTO tree_nodes(node_id, parent, type, name, diagram_id)
            VALUES (1, 0, 'item', NULL, 1)
            """
        )
        for row in icon_rows + line_rows:
            _insert_item(db, **row)
        db.execute(
            "INSERT INTO diagram_info(diagram_id, name, value) VALUES (1, ?, ?)",
            (
                MAP_SCHEMA,
                json.dumps(mapping, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            ),
        )

    return mapping


def _load_projection(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a DRAKON Editor .drn SQLite file from O3a projection JSON"
    )
    parser.add_argument("projection", help="projection JSON path, or - for stdin")
    parser.add_argument("output", help="output .drn path")
    args = parser.parse_args()
    try:
        projection = _load_projection(args.projection)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_projection(projection, output)
    except (OSError, sqlite3.Error, json.JSONDecodeError, WriterError) as exc:
        print(f"DRAKON writer error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
