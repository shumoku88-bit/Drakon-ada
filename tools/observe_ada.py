#!/usr/bin/env python3
"""Observe Ada/SPARK control flow without making DRAKON authoritative.

Phase O2: Libadalang parses one Ada source file and this tool emits a small,
deterministic renderer-independent control-flow graph with exact source spans.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "drakon-ada/control-flow-observation/v1"

SUPPORTED_ACTION_KINDS = {
    "AssignStmt",
    "CallStmt",
    "NullStmt",
}


class ObservationError(RuntimeError):
    pass


def load_libadalang():
    try:
        import libadalang as lal
    except ModuleNotFoundError as exc:
        raise ObservationError(
            "Libadalang Python bindings are unavailable; install a qualified "
            "Libadalang toolchain before running the source observer"
        ) from exc
    return lal


def relative_source_path(source: Path, source_root: Path) -> str:
    source = source.resolve()
    source_root = source_root.resolve()
    try:
        return source.relative_to(source_root).as_posix()
    except ValueError as exc:
        raise ObservationError(
            f"source {source} is outside --source-root {source_root}"
        ) from exc


def source_span(node) -> dict:
    span = node.sloc_range
    return {
        "start": {"line": span.start.line, "column": span.start.column},
        "end": {"line": span.end.line, "column": span.end.column},
    }


def statement_key(statement) -> tuple:
    span = statement.sloc_range
    return (
        type(statement).__name__,
        span.start.line,
        span.start.column,
        span.end.line,
        span.end.column,
    )


def direct_statements(container) -> list:
    if container is None:
        return []
    return list(container)


class GraphBuilder:
    def __init__(self, body):
        self.body_span = source_span(body)
        self.nodes = [
            {
                "id": "entry",
                "kind": "entry",
                "origin": "synthetic",
                "span": self.body_span,
                "text": "entry",
            }
        ]
        self.edges = []
        self.node_ids = {}
        self.next_node_number = 1

    def add_edge(self, source: str, target: str, role: str) -> None:
        self.edges.append({"from": source, "to": target, "role": role})

    def source_node(self, statement, kind: str, *, label_node=None) -> str:
        key = statement_key(statement)
        existing = self.node_ids.get(key)
        if existing is not None:
            return existing

        node_id = f"n{self.next_node_number:04d}"
        self.next_node_number += 1
        node = {
            "id": node_id,
            "kind": kind,
            "origin": "source",
            "ada_kind": type(statement).__name__,
            "span": source_span(statement),
            "text": statement.text,
        }
        if label_node is not None:
            node["label"] = label_node.text
            node["label_span"] = source_span(label_node)
        self.node_ids[key] = node_id
        self.nodes.append(node)
        return node_id

    def register_sequence(self, statements) -> None:
        """Register supported source nodes in deterministic source preorder."""
        for statement in direct_statements(statements):
            ada_kind = type(statement).__name__
            if ada_kind in SUPPORTED_ACTION_KINDS:
                self.source_node(statement, "action")
            elif ada_kind == "ReturnStmt":
                self.source_node(statement, "return")
            elif ada_kind == "IfStmt":
                if len(statement.f_alternatives) != 0:
                    raise ObservationError(
                        "unsupported control-flow construct ElsifStmtPart "
                        f"at {source_span(statement)}"
                    )
                self.source_node(
                    statement, "decision", label_node=statement.f_cond_expr
                )
                self.register_sequence(statement.f_then_stmts)
                if statement.f_else_part is not None:
                    self.register_sequence(statement.f_else_part.f_stmts)
            elif ada_kind == "WhileLoopStmt":
                self.source_node(
                    statement, "loop", label_node=statement.f_spec.f_expr
                )
                self.register_sequence(statement.f_stmts)
            else:
                raise ObservationError(
                    f"unsupported control-flow statement {ada_kind} "
                    f"at {source_span(statement)}"
                )

    def build_sequence(
        self, statements, continuation: str, continuation_role: str = "next"
    ) -> str:
        """Build one structured sequence backwards toward its continuation."""
        current = continuation
        current_role = continuation_role
        for statement in reversed(direct_statements(statements)):
            ada_kind = type(statement).__name__
            node_id = self.node_ids[statement_key(statement)]

            if ada_kind in SUPPORTED_ACTION_KINDS:
                self.add_edge(node_id, current, current_role)
                current = node_id
                current_role = "next"
            elif ada_kind == "ReturnStmt":
                self.add_edge(node_id, "exit", "return")
                current = node_id
                current_role = "next"
            elif ada_kind == "IfStmt":
                then_entry = self.build_sequence(
                    statement.f_then_stmts, current, current_role
                )
                if statement.f_else_part is None:
                    else_entry = current
                else:
                    else_entry = self.build_sequence(
                        statement.f_else_part.f_stmts, current, current_role
                    )
                self.add_edge(node_id, then_entry, "true")
                self.add_edge(node_id, else_entry, "false")
                current = node_id
                current_role = "next"
            elif ada_kind == "WhileLoopStmt":
                body_entry = self.build_sequence(
                    statement.f_stmts, node_id, "back"
                )
                self.add_edge(node_id, body_entry, "loop_body")
                self.add_edge(node_id, current, "loop_exit")
                current = node_id
                current_role = "next"
            else:
                raise AssertionError(
                    f"unsupported statement reached graph builder: {ada_kind}"
                )
        return current

    def finish(self, statements) -> dict:
        self.register_sequence(statements)
        self.nodes.append(
            {
                "id": "exit",
                "kind": "exit",
                "origin": "synthetic",
                "span": self.body_span,
                "text": "exit",
            }
        )
        first = self.build_sequence(statements, "exit")
        self.add_edge("entry", first, "next")

        node_order = {node["id"]: index for index, node in enumerate(self.nodes)}
        role_order = {
            "next": 0,
            "true": 1,
            "false": 2,
            "loop_body": 3,
            "loop_exit": 4,
            "back": 5,
            "return": 6,
        }
        self.edges.sort(
            key=lambda edge: (
                node_order[edge["from"]],
                role_order[edge["role"]],
                node_order[edge["to"]],
            )
        )

        graph = {
            "entry_node": "entry",
            "exit_node": "exit",
            "nodes": self.nodes,
            "edges": self.edges,
        }
        validate_graph(graph)
        return graph


def validate_graph(graph: dict) -> None:
    ids = [node["id"] for node in graph["nodes"]]
    if len(ids) != len(set(ids)):
        raise ObservationError("normalized graph contains duplicate node ids")

    node_ids = set(ids)
    for endpoint in ("entry_node", "exit_node"):
        if graph[endpoint] not in node_ids:
            raise ObservationError(f"normalized graph has missing {endpoint}")

    seen_edges = set()
    for edge in graph["edges"]:
        if edge["from"] not in node_ids or edge["to"] not in node_ids:
            raise ObservationError(f"normalized graph has dangling edge: {edge}")
        key = (edge["from"], edge["to"], edge["role"])
        if key in seen_edges:
            raise ObservationError(f"normalized graph has duplicate edge: {edge}")
        seen_edges.add(key)


def observe(source: Path, source_root: Path, charset: str = "utf-8", lal=None) -> dict:
    source = source.resolve()
    source_root = source_root.resolve()
    if not source.is_file():
        raise ObservationError(f"source file does not exist: {source}")

    source_path = relative_source_path(source, source_root)
    lal = lal or load_libadalang()
    context = lal.AnalysisContext(charset=charset)
    unit = context.get_from_file(str(source))

    if unit.diagnostics:
        rendered = " | ".join(str(diagnostic) for diagnostic in unit.diagnostics)
        raise ObservationError(f"Libadalang diagnostics: {rendered}")
    if unit.root is None:
        raise ObservationError("Libadalang returned no syntax tree")

    bodies = unit.root.findall(lal.SubpBody)
    if len(bodies) != 1:
        raise ObservationError(
            "Phase O2 observes exactly one SubpBody per source file; "
            f"found {len(bodies)}"
        )

    body = bodies[0]
    name_node = body.f_subp_spec.f_subp_name
    if name_node is None:
        raise ObservationError("subprogram body has no explicit source name")

    handled = body.f_stmts
    if handled is None:
        raise ObservationError("subprogram body has no handled statements")
    if len(handled.f_exceptions) != 0:
        raise ObservationError(
            "exception handlers are unsupported in the Phase O2 control-flow slice"
        )

    graph = GraphBuilder(body).finish(handled.f_stmts)
    source_bytes = source.read_bytes()
    return {
        "schema": SCHEMA,
        "complete": True,
        "frontend": {
            "name": "libadalang",
            "version": getattr(lal, "__version__", "unknown"),
        },
        "options": {"charset": charset},
        "source": {
            "path": source_path,
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        },
        "subprogram": {
            "name": name_node.text,
            "span": source_span(body),
        },
        **graph,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Emit a Libadalang-backed normalized control-flow observation"
    )
    parser.add_argument("source", type=Path, help="Ada source file to observe")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT,
        help="root used for stable source identity (default: Drakon-ada root)",
    )
    parser.add_argument(
        "--charset",
        default="utf-8",
        help="source charset passed explicitly to Libadalang (default: utf-8)",
    )
    parser.add_argument(
        "--pretty", action="store_true", help="pretty-print JSON for human inspection"
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        observation = observe(args.source, args.source_root, args.charset)
    except ObservationError as exc:
        print(f"observe_ada: {exc}", file=sys.stderr)
        return 2

    if args.pretty:
        print(json.dumps(observation, indent=2, sort_keys=True))
    else:
        print(json.dumps(observation, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
