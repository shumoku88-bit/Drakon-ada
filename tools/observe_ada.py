#!/usr/bin/env python3
"""Observe Ada/SPARK source structure without making DRAKON authoritative.

Phase O1 probe: Libadalang parses one Ada source file and this tool emits a
small, deterministic JSON observation containing exact source spans for the
subprogram and its statements.  No control-flow edges are inferred yet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "drakon-ada/source-observation/v1"


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


def normalized_kind(ada_kind: str) -> str:
    if ada_kind == "IfStmt":
        return "decision"
    if ada_kind in {"WhileLoopStmt", "ForLoopStmt", "LoopStmt"}:
        return "loop"
    if ada_kind in {"ReturnStmt", "ExtendedReturnStmt"}:
        return "return"
    return "action"


def observe(source: Path, source_root: Path, lal=None) -> dict:
    source = source.resolve()
    source_root = source_root.resolve()
    if not source.is_file():
        raise ObservationError(f"source file does not exist: {source}")

    source_path = relative_source_path(source, source_root)
    lal = lal or load_libadalang()
    context = lal.AnalysisContext()
    unit = context.get_from_file(str(source))

    if unit.diagnostics:
        rendered = " | ".join(str(diagnostic) for diagnostic in unit.diagnostics)
        raise ObservationError(f"Libadalang diagnostics: {rendered}")
    if unit.root is None:
        raise ObservationError("Libadalang returned no syntax tree")

    bodies = unit.root.findall(lal.SubpBody)
    if len(bodies) != 1:
        raise ObservationError(
            "Phase O1 observes exactly one SubpBody per source file; "
            f"found {len(bodies)}"
        )

    body = bodies[0]
    spec = body.f_subp_spec
    name_node = spec.f_subp_name
    if name_node is None:
        raise ObservationError("subprogram body has no explicit source name")

    nodes = []
    for index, statement in enumerate(body.findall(lal.Stmt), start=1):
        ada_kind = type(statement).__name__
        nodes.append(
            {
                "id": f"n{index:04d}",
                "kind": normalized_kind(ada_kind),
                "ada_kind": ada_kind,
                "span": source_span(statement),
                "text": statement.text,
            }
        )

    source_bytes = source.read_bytes()
    return {
        "schema": SCHEMA,
        "frontend": {
            "name": "libadalang",
            "version": getattr(lal, "__version__", "unknown"),
        },
        "source": {
            "path": source_path,
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        },
        "subprogram": {
            "name": name_node.text,
            "span": source_span(body),
        },
        "nodes": nodes,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Emit a Libadalang-backed source observation as JSON"
    )
    parser.add_argument("source", type=Path, help="Ada source file to observe")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT,
        help="root used for stable source identity (default: Drakon-ada root)",
    )
    parser.add_argument(
        "--pretty", action="store_true", help="pretty-print JSON for human inspection"
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        observation = observe(args.source, args.source_root)
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
