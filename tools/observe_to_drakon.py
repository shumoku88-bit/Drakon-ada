#!/usr/bin/env python3
"""Observe one Ada/SPARK source file and write its derived DRAKON document."""

from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any, Callable

import observe_ada
import project_drakon
import write_drakon

ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = ROOT / "build" / "drakon"


class PipelineError(RuntimeError):
    """Raised when orchestration metadata is unsafe or incomplete."""


def _default_output(observation: dict[str, Any]) -> Path:
    source = observation.get("source")
    if not isinstance(source, dict):
        raise PipelineError("observation is missing source identity")
    source_path = source.get("path")
    if not isinstance(source_path, str) or not source_path:
        raise PipelineError("observation source path must be a non-empty string")

    relative = Path(source_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise PipelineError(f"unsafe observation source path: {source_path!r}")
    return BUILD_ROOT / relative.with_suffix(".drn")


def observe_to_drakon(
    source: Path,
    *,
    source_root: Path = ROOT,
    output: Path | None = None,
    charset: str = "utf-8",
    observer: Callable[..., dict[str, Any]] | None = None,
    projector: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    writer: Callable[[dict[str, Any], Path], Any] | None = None,
) -> Path:
    """Compose the qualified observer, projector, and writer without new semantics."""

    source = Path(source)
    source_root = Path(source_root)
    observer = observer or observe_ada.observe
    projector = projector or project_drakon.project_observation
    writer = writer or write_drakon.write_projection

    observation = observer(source, source_root, charset)
    projection = projector(observation)

    destination = Path(output) if output is not None else _default_output(observation)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        delete=False,
    ) as handle:
        temporary = Path(handle.name)

    try:
        writer(projection, temporary)
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()

    return destination


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Observe Ada/SPARK control flow and write a derived DRAKON Editor document"
    )
    parser.add_argument("source", type=Path, help="Ada source file to observe")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT,
        help="root used for stable source identity (default: Drakon-ada root)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="output .drn path (default: build/drakon/<source identity>.drn)",
    )
    parser.add_argument(
        "--charset",
        default="utf-8",
        help="source charset passed to the qualified observer (default: utf-8)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        output = observe_to_drakon(
            args.source,
            source_root=args.source_root,
            output=args.output,
            charset=args.charset,
        )
    except (
        OSError,
        sqlite3.Error,
        PipelineError,
        observe_ada.ObservationError,
        project_drakon.ProjectionError,
        write_drakon.WriterError,
    ) as exc:
        print(f"observe_to_drakon: {exc}", file=sys.stderr)
        return 2

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
