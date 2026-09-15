#!/usr/bin/env python3
"""Fail-closed qualification gate for the active Ada/SPARK source observer.

Unlike the unittest module, this gate never treats a missing Libadalang binding
as a successful skip. It records the exact runtime environment and requires the
qualified fixture to reproduce byte-for-byte deterministic normalized control
flow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/source-observation/observation_fixture.adb"
OBSERVER = ROOT / "tools/observe_ada.py"
SCHEMA = "drakon-ada/control-flow-observation/v1"


class QualificationError(RuntimeError):
    pass


def run(args, *, ok=True):
    result = subprocess.run(
        list(map(str, args)),
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if ok and result.returncode != 0:
        raise QualificationError(
            f"command failed ({result.returncode}): {' '.join(map(str, args))}\n"
            f"{result.stdout}{result.stderr}"
        )
    if not ok and result.returncode == 0:
        raise QualificationError(
            f"command unexpectedly succeeded: {' '.join(map(str, args))}"
        )
    return result


def load_frontend():
    try:
        import libadalang as lal
    except Exception as exc:  # missing module and dynamic-loader failures are fatal here
        raise QualificationError(f"Libadalang import failed: {exc}") from exc
    return lal


def observe_bytes() -> bytes:
    result = run(
        [
            sys.executable,
            OBSERVER,
            SOURCE,
            "--source-root",
            ROOT,
        ]
    )
    return result.stdout.encode("utf-8")


def qualify() -> dict:
    lal = load_frontend()

    tests = run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_source_observation.py",
            "-v",
        ]
    )

    first = observe_bytes()
    second = observe_bytes()
    if first != second:
        raise QualificationError("observer output changed between identical runs")

    observation = json.loads(first)
    if observation.get("schema") != SCHEMA:
        raise QualificationError(f"unexpected schema: {observation.get('schema')!r}")
    if observation.get("complete") is not True:
        raise QualificationError("fixture observation is not marked complete")
    if observation.get("entry_node") != "entry" or observation.get("exit_node") != "exit":
        raise QualificationError("fixture entry/exit identity changed")
    if len(observation.get("nodes", [])) != 11:
        raise QualificationError("fixture must contain 11 normalized nodes")
    if len(observation.get("edges", [])) != 13:
        raise QualificationError("fixture must contain 13 normalized edges")

    roles = {edge["role"] for edge in observation["edges"]}
    expected_roles = {
        "next",
        "true",
        "false",
        "loop_body",
        "loop_exit",
        "back",
        "return",
    }
    if roles != expected_roles:
        raise QualificationError(
            f"fixture edge roles changed: expected {sorted(expected_roles)}, got {sorted(roles)}"
        )

    frontend_version = getattr(lal, "__version__", "unknown")
    module_path = getattr(lal, "__file__", "unknown")
    return {
        "qualification": "drakon-ada/source-observer/v1",
        "result": "pass",
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "release": platform.release(),
            "python": sys.version.split()[0],
        },
        "frontend": {
            "name": "libadalang",
            "version": frontend_version,
            "module": module_path,
        },
        "fixture": {
            "source": SOURCE.relative_to(ROOT).as_posix(),
            "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "observation_sha256": hashlib.sha256(first).hexdigest(),
            "nodes": len(observation["nodes"]),
            "edges": len(observation["edges"]),
        },
        "tests": {
            "command": "python -m unittest discover -s tests -p test_source_observation.py -v",
            "stderr": tests.stderr,
        },
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Qualify the Libadalang source observer")
    parser.add_argument(
        "--evidence",
        type=Path,
        help="optional path to write the qualification evidence JSON",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        evidence = qualify()
    except QualificationError as exc:
        print(f"qualify_source_observer: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.evidence is not None:
        path = args.evidence.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
