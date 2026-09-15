#!/usr/bin/env python3
"""Project normalized control flow into a deterministic DRAKON-oriented model."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
import sys
from typing import Any

INPUT_SCHEMA = "drakon-ada/control-flow-observation/v1"
OUTPUT_SCHEMA = "drakon-ada/drakon-projection/v1"

ALLOWED_KINDS = {"entry", "exit", "action", "decision", "loop", "return"}
ALLOWED_ROLES = {
    "next",
    "true",
    "false",
    "loop_body",
    "loop_exit",
    "back",
    "return",
}
ICON_BY_KIND = {
    "entry": "beginend",
    "exit": "beginend",
    "action": "action",
    "decision": "if",
    "loop": "if",
    "return": "action",
}

BASE_X = 240
BASE_Y = 100
LANE_SPACING = 260
RANK_SPACING = 120


class ProjectionError(ValueError):
    """Raised when the normalized observation cannot be projected safely."""


def _node_text(node: dict[str, Any], subprogram_name: str) -> str:
    kind = node["kind"]
    if kind == "entry":
        return subprogram_name
    if kind == "exit":
        return "end"
    if kind in {"decision", "loop"}:
        label = node.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ProjectionError(f"{node['id']}: {kind} node is missing a label")
        return label.strip()
    text = node.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ProjectionError(f"{node['id']}: source node is missing text")
    return text.strip()


def _require_role_contract(
    node: dict[str, Any],
    outgoing: list[dict[str, Any]],
    exit_node: str,
) -> None:
    node_id = node["id"]
    kind = node["kind"]
    roles = [edge["role"] for edge in outgoing]

    if kind == "entry":
        if roles != ["next"]:
            raise ProjectionError(f"{node_id}: entry must have exactly one next edge")
    elif kind == "exit":
        if roles:
            raise ProjectionError(f"{node_id}: exit must not have outgoing edges")
    elif kind == "decision":
        if sorted(roles) != ["false", "true"]:
            raise ProjectionError(
                f"{node_id}: decision must have exactly one true and one false edge"
            )
    elif kind == "loop":
        if sorted(roles) != ["loop_body", "loop_exit"]:
            raise ProjectionError(
                f"{node_id}: loop must have exactly one loop_body and one loop_exit edge"
            )
    elif kind == "return":
        if len(outgoing) != 1 or outgoing[0]["role"] != "return":
            raise ProjectionError(f"{node_id}: return must have exactly one return edge")
        if outgoing[0]["to"] != exit_node:
            raise ProjectionError(f"{node_id}: return edge must target the synthetic exit")
    elif kind == "action":
        if len(outgoing) != 1 or outgoing[0]["role"] not in {"next", "back"}:
            raise ProjectionError(
                f"{node_id}: action must have exactly one next or back edge"
            )


def _validate_observation(
    observation: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if observation.get("schema") != INPUT_SCHEMA:
        raise ProjectionError(f"unsupported observation schema: {observation.get('schema')!r}")
    if observation.get("complete") is not True:
        raise ProjectionError("observation must be complete before projection")

    nodes = observation.get("nodes")
    edges = observation.get("edges")
    if not isinstance(nodes, list) or not nodes:
        raise ProjectionError("observation nodes must be a non-empty list")
    if not isinstance(edges, list):
        raise ProjectionError("observation edges must be a list")

    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ProjectionError("every node must be an object")
        node_id = node.get("id")
        kind = node.get("kind")
        origin = node.get("origin")
        if not isinstance(node_id, str) or not node_id:
            raise ProjectionError("every node must have a non-empty string id")
        if node_id in by_id:
            raise ProjectionError(f"duplicate node id: {node_id}")
        if kind not in ALLOWED_KINDS:
            raise ProjectionError(f"{node_id}: unsupported normalized node kind {kind!r}")
        if origin not in {"synthetic", "source"}:
            raise ProjectionError(f"{node_id}: unsupported node origin {origin!r}")
        if kind in {"entry", "exit"} and origin != "synthetic":
            raise ProjectionError(f"{node_id}: {kind} node must be synthetic")
        if kind not in {"entry", "exit"} and origin != "source":
            raise ProjectionError(f"{node_id}: source control-flow node must retain source origin")
        by_id[node_id] = node

    entry_node = observation.get("entry_node")
    exit_node = observation.get("exit_node")
    if entry_node not in by_id or by_id[entry_node]["kind"] != "entry":
        raise ProjectionError("entry_node must reference the synthetic entry node")
    if exit_node not in by_id or by_id[exit_node]["kind"] != "exit":
        raise ProjectionError("exit_node must reference the synthetic exit node")

    seen_edges: set[tuple[str, str, str]] = set()
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming_back_targets: set[str] = set()

    for edge in edges:
        if not isinstance(edge, dict):
            raise ProjectionError("every edge must be an object")
        source = edge.get("from")
        target = edge.get("to")
        role = edge.get("role")
        if source not in by_id or target not in by_id:
            raise ProjectionError(f"dangling edge: {source!r} -> {target!r}")
        if role not in ALLOWED_ROLES:
            raise ProjectionError(f"{source}->{target}: unsupported edge role {role!r}")
        key = (source, target, role)
        if key in seen_edges:
            raise ProjectionError(f"duplicate edge: {source}->{target} ({role})")
        seen_edges.add(key)
        outgoing[source].append(edge)
        if role == "back":
            incoming_back_targets.add(target)

    for node in nodes:
        _require_role_contract(node, outgoing[node["id"]], exit_node)

    for node in nodes:
        if node["kind"] == "loop" and node["id"] not in incoming_back_targets:
            raise ProjectionError(f"{node['id']}: loop has no back edge")

    return nodes, edges, by_id


def _layout(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    entry_node: str,
) -> tuple[dict[str, dict[str, int | bool]], list[str]]:
    order = {node["id"]: index for index, node in enumerate(nodes)}
    forward_edges = [edge for edge in edges if edge["role"] != "back"]

    indegree = {node["id"]: 0 for node in nodes}
    adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in forward_edges:
        indegree[edge["to"]] += 1
        adjacency[edge["from"]].append(edge)

    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    ready.sort(key=order.__getitem__)
    topo: list[str] = []
    queue = deque(ready)
    while queue:
        node_id = queue.popleft()
        topo.append(node_id)
        released: list[str] = []
        for edge in sorted(
            adjacency[node_id],
            key=lambda item: (order[item["to"]], item["role"]),
        ):
            target = edge["to"]
            indegree[target] -= 1
            if indegree[target] == 0:
                released.append(target)
        if released:
            current = list(queue)
            current.extend(released)
            current.sort(key=order.__getitem__)
            queue = deque(current)

    if len(topo) != len(nodes):
        raise ProjectionError("forward control-flow graph contains a cycle not marked as back")

    reachable: set[str] = set()
    pending = [entry_node]
    all_adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        all_adjacency[edge["from"]].append(edge["to"])
    while pending:
        node_id = pending.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        pending.extend(all_adjacency[node_id])

    rank: dict[str, int] = {entry_node: 0}
    lane: dict[str, int] = {entry_node: 0}
    incoming_forward: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in forward_edges:
        incoming_forward[edge["to"]].append(edge)

    for node_id in topo:
        if node_id == entry_node or node_id not in reachable:
            continue
        predecessors = [
            edge for edge in incoming_forward[node_id] if edge["from"] in reachable
        ]
        if not predecessors:
            continue

        rank[node_id] = max(rank.get(edge["from"], 0) + 1 for edge in predecessors)

        candidates: list[int] = []
        for edge in predecessors:
            source_lane = lane.get(edge["from"], 0)
            if edge["role"] in {"true", "loop_body"}:
                candidates.append(source_lane + 1)
            else:
                candidates.append(source_lane)
        lane[node_id] = min(candidates)

    detached_rank = max(rank.values(), default=0) + 1
    positions: dict[str, dict[str, int | bool]] = {}
    detached_nodes: list[str] = []
    for node in nodes:
        node_id = node["id"]
        is_reachable = node_id in reachable
        if is_reachable:
            node_rank = rank.get(node_id, 0)
            node_lane = lane.get(node_id, 0)
        else:
            node_rank = detached_rank + len(detached_nodes)
            node_lane = -1
            detached_nodes.append(node_id)

        positions[node_id] = {
            "x": BASE_X + node_lane * LANE_SPACING,
            "y": BASE_Y + node_rank * RANK_SPACING,
            "rank": node_rank,
            "lane": node_lane,
            "reachable": is_reachable,
        }

    return positions, detached_nodes


def project_observation(observation: dict[str, Any]) -> dict[str, Any]:
    nodes, edges, by_id = _validate_observation(observation)

    subprogram = observation.get("subprogram")
    if not isinstance(subprogram, dict) or not isinstance(subprogram.get("name"), str):
        raise ProjectionError("observation must carry a subprogram name")
    subprogram_name = subprogram["name"]

    entry_node = observation["entry_node"]
    positions, detached_nodes = _layout(nodes, edges, entry_node)

    projected_nodes = []
    for index, node in enumerate(nodes):
        node_id = node["id"]
        trace: dict[str, Any] | None
        if node["origin"] == "source":
            trace = {
                "ada_kind": node.get("ada_kind"),
                "span": node.get("span"),
                "source_text": node.get("text"),
            }
        else:
            trace = None

        projected_nodes.append(
            {
                "id": node_id,
                "semantic_kind": node["kind"],
                "icon": ICON_BY_KIND[node["kind"]],
                "text": _node_text(node, subprogram_name),
                "origin": node["origin"],
                "trace": trace,
                "layout": positions[node_id],
                "order": index,
            }
        )

    projected_edges = [
        {
            "from": edge["from"],
            "to": edge["to"],
            "role": edge["role"],
            "back": edge["role"] == "back",
        }
        for edge in edges
    ]

    return {
        "schema": OUTPUT_SCHEMA,
        "source_observation_schema": INPUT_SCHEMA,
        "source": observation.get("source"),
        "subprogram": subprogram,
        "entry_node": observation["entry_node"],
        "exit_node": observation["exit_node"],
        "layout": {
            "strategy": "structured-lanes/v1",
            "base_x": BASE_X,
            "base_y": BASE_Y,
            "lane_spacing": LANE_SPACING,
            "rank_spacing": RANK_SPACING,
            "detached_nodes": detached_nodes,
        },
        "nodes": projected_nodes,
        "edges": projected_edges,
    }


def _load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def _dump_json(projection: dict[str, Any], path: str) -> None:
    text = json.dumps(projection, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path == "-":
        sys.stdout.write(text)
    else:
        Path(path).write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Project normalized Drakon-ada control flow into DRAKON-oriented JSON"
    )
    parser.add_argument("observation", help="normalized observation JSON path, or - for stdin")
    parser.add_argument(
        "--output",
        "-o",
        default="-",
        help="projection JSON path, or - for stdout (default)",
    )
    args = parser.parse_args()

    try:
        observation = _load_json(args.observation)
        projection = project_observation(observation)
        _dump_json(projection, args.output)
    except (OSError, json.JSONDecodeError, ProjectionError) as exc:
        print(f"projection error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
