#!/usr/bin/env python3
"""Generate a human and machine-readable map of the Drakon-ada repository.

The map has two jobs:

1. show the tracked repository tree and the canonical DRAKON sources in one place;
2. expose the semantic/geometry information stored inside each ``.drn`` SQLite
   document so review does not normally require screenshots.

By default only checked-in ``examples/**/*.drn`` files are mapped. Pass
``--include-build`` to include positive working copies under ``build/`` while
skipping generated output, evidence, and negative-control directories.

Outputs are intentionally written under ``build/`` by default. They are derived
review artifacts, not canonical sources.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "build"
SKIP_BUILD_PARTS = {
    "bin",
    "obj",
    "evidence",
    "generated",
    "generated-final",
    "negative",
    "negative-pairing",
    "negative-condition-pairing",
    "negative-pairing-witness",
    "off-by-one-active-bound",
    "inactive-tail-folded",
    "too-narrow-total",
    "weak-invariant",
}
TEXT_REFERENCE_ROOTS = ("docs", "tests", "tools", "generator")


def git_output(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


def tracked_files(root: Path) -> list[str]:
    try:
        raw = git_output(root, "ls-files")
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.parts and "build" not in path.parts
        )
    return [line for line in raw.splitlines() if line]


def git_head(root: Path) -> str | None:
    try:
        return git_output(root, "rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        return None


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return (
        db.execute(
            "select 1 from sqlite_master where type='table' and name=?", (name,)
        ).fetchone()
        is not None
    )


def query_dicts(db: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    cursor = db.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def metadata_summary(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    wanted = {"schema", "profile", "package", "always_terminates"}
    summary: dict[str, str] = {}
    for line in raw.splitlines():
        key, sep, value = line.partition(" ")
        if sep and key in wanted:
            summary[key] = value.strip()
    return summary


def inspect_drn(path: Path, root: Path, source_kind: str) -> dict[str, Any]:
    rel = str(path.relative_to(root))
    uri = f"file:{path}?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        diagrams = (
            query_dicts(
                db,
                "select diagram_id, name, origin, description, zoom "
                "from diagrams order by diagram_id",
            )
            if table_exists(db, "diagrams")
            else []
        )
        items = (
            query_dicts(
                db,
                "select item_id, diagram_id, type, text, selected, x, y, w, h, "
                "a, b, aux_value, color, format, text2 "
                "from items order by diagram_id, y, x, item_id",
            )
            if table_exists(db, "items")
            else []
        )
        tree_nodes = (
            query_dicts(
                db,
                "select node_id, parent, type, name, diagram_id "
                "from tree_nodes order by node_id",
            )
            if table_exists(db, "tree_nodes")
            else []
        )
        diagram_info_rows = (
            query_dicts(
                db,
                "select diagram_id, name, value from diagram_info "
                "order by diagram_id, name",
            )
            if table_exists(db, "diagram_info")
            else []
        )
        global_info_rows = (
            query_dicts(db, "select key, value from info order by key")
            if table_exists(db, "info")
            else []
        )

    by_diagram: dict[int, dict[str, Any]] = {
        diagram["diagram_id"]: {
            **diagram,
            "items": [],
            "tree_nodes": [],
            "diagram_info": {},
            "ada": {},
        }
        for diagram in diagrams
    }
    for item in items:
        if item["diagram_id"] in by_diagram:
            by_diagram[item["diagram_id"]]["items"].append(item)
    for node in tree_nodes:
        diagram_id = node.get("diagram_id")
        if diagram_id in by_diagram:
            by_diagram[diagram_id]["tree_nodes"].append(node)
    for row in diagram_info_rows:
        diagram_id = row["diagram_id"]
        if diagram_id in by_diagram:
            by_diagram[diagram_id]["diagram_info"][row["name"]] = row["value"]
            if row["name"] == "ada":
                by_diagram[diagram_id]["ada"] = metadata_summary(row["value"])

    return {
        "source": rel,
        "source_kind": source_kind,
        "sha256": file_digest(path),
        "global_info": {row["key"]: row["value"] for row in global_info_rows},
        "diagrams": list(by_diagram.values()),
        "references": [],
    }


def positive_build_drn(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root / "build")
    except ValueError:
        return False
    return not any(part in SKIP_BUILD_PARTS or part.startswith("negative-") for part in rel.parts)


def drn_sources(root: Path, include_build: bool) -> list[tuple[Path, str]]:
    result: list[tuple[Path, str]] = []
    examples = root / "examples"
    if examples.exists():
        result.extend((path, "canonical") for path in sorted(examples.rglob("*.drn")))
    if include_build:
        build = root / "build"
        if build.exists():
            result.extend(
                (path, "working")
                for path in sorted(build.rglob("*.drn"))
                if positive_build_drn(path, root)
            )
    return result


def reference_files(root: Path, tracked: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for rel in tracked:
        parts = Path(rel).parts
        if not parts or parts[0] not in TEXT_REFERENCE_ROOTS:
            continue
        path = root / rel
        try:
            if path.stat().st_size > 1_000_000:
                continue
            result[rel] = path.read_text(errors="ignore")
        except (OSError, UnicodeError):
            continue
    return result


def attach_references(entries: list[dict[str, Any]], texts: dict[str, str]) -> None:
    for entry in entries:
        source = entry["source"]
        filename = Path(source).name
        refs = []
        for rel, text in texts.items():
            if source in text or filename in text:
                refs.append(rel)
        entry["references"] = sorted(refs)


def make_tree(paths: Iterable[str]) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for raw in sorted(paths):
        node = tree
        for part in Path(raw).parts:
            node = node.setdefault(part, {})
    return tree


def render_tree(node: dict[str, Any], prefix: str = "") -> list[str]:
    lines: list[str] = []
    items = list(node.items())
    for index, (name, child) in enumerate(items):
        last = index == len(items) - 1
        branch = "└── " if last else "├── "
        lines.append(prefix + branch + name)
        extension = "    " if last else "│   "
        lines.extend(render_tree(child, prefix + extension))
    return lines


def one_line(text: str) -> str:
    return " ".join(text.split())


def flow_items(diagram: dict[str, Any]) -> list[dict[str, Any]]:
    visible = {"beginend", "action", "if"}
    return [item for item in diagram["items"] if item["type"] in visible]


def render_markdown(model: dict[str, Any]) -> str:
    lines = [
        "# Drakon-ada repository map",
        "",
        "> Derived review artifact. Canonical meaning remains in the checked-in",
        "> repository sources, especially each `.drn` file and its explicit metadata.",
        "",
        f"Git HEAD: `{model['repository']['git_head'] or 'unknown'}`",
        "",
        "## Tracked repository tree",
        "",
        "```text",
        model["repository"]["name"],
    ]
    lines.extend(render_tree(make_tree(model["tracked_files"])))
    lines.extend(["```", "", "## DRAKON diagram index", ""])

    if not model["drn_sources"]:
        lines.append("No DRAKON sources found.")
        return "\n".join(lines) + "\n"

    for entry in model["drn_sources"]:
        marker = "canonical" if entry["source_kind"] == "canonical" else "working"
        lines.extend(
            [
                f"### `{entry['source']}`",
                "",
                f"Source kind: **{marker}**  ",
                f"SHA-256: `{entry['sha256']}`",
                "",
            ]
        )
        if entry["references"]:
            lines.append("Repository references:")
            for ref in entry["references"]:
                lines.append(f"- `{ref}`")
            lines.append("")

        for diagram in entry["diagrams"]:
            ada = diagram.get("ada", {})
            lines.append(f"#### Diagram `{diagram['name']}`")
            lines.append("")
            if diagram.get("description"):
                lines.append(f"Description: {diagram['description']}")
                lines.append("")
            if ada:
                facts = []
                for key in ("profile", "schema", "package", "always_terminates"):
                    if key in ada:
                        facts.append(f"{key}=`{ada[key]}`")
                if facts:
                    lines.append("Ada/SPARK metadata: " + ", ".join(facts))
                    lines.append("")
            lines.append("Visual-semantic inventory, ordered top-to-bottom by stored geometry:")
            lines.append("")
            for item in flow_items(diagram):
                text = one_line(item.get("text") or "")
                geometry = (
                    f"x={item['x']}, y={item['y']}, w={item['w']}, h={item['h']}"
                )
                lines.append(
                    f"- `{item['type']}` #{item['item_id']}: `{text}` ({geometry})"
                )
            lines.append("")

    lines.extend(
        [
            "## Review boundary",
            "",
            "The map is sufficient for normal semantic, topology, contract, proof-owner,",
            "and stored-geometry review. A GUI screenshot is still the authority for",
            "font fit, rendered line clearance, and human reading flow.",
            "",
        ]
    )
    return "\n".join(lines)


def build_model(root: Path, include_build: bool) -> dict[str, Any]:
    tracked = tracked_files(root)
    entries = [
        inspect_drn(path, root, source_kind)
        for path, source_kind in drn_sources(root, include_build)
    ]
    attach_references(entries, reference_files(root, tracked))
    return {
        "schema": 1,
        "repository": {"name": root.name, "git_head": git_head(root)},
        "tracked_files": tracked,
        "drn_sources": entries,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="derived output directory (default: build/)",
    )
    parser.add_argument(
        "--include-build",
        action="store_true",
        help="also map positive working .drn files under build/",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    model = build_model(root, args.include_build)
    json_path = output_dir / "repository-map.json"
    markdown_path = output_dir / "repository-map.md"
    json_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")
    markdown_path.write_text(render_markdown(model))

    canonical = sum(1 for source in model["drn_sources"] if source["source_kind"] == "canonical")
    working = sum(1 for source in model["drn_sources"] if source["source_kind"] == "working")
    print(f"repository map: {canonical} canonical, {working} working DRAKON source(s)")
    print(markdown_path)
    print(json_path)


if __name__ == "__main__":
    main()
