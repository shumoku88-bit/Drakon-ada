#!/usr/bin/env python3
"""Repository discovery and navigation catalog generator for DRAKON Editor.

Discovers canonical DRAKON sources under ``examples/`` and positive working
copies under ``build/``, extracting diagram names and metadata for the
in-editor Repository Browser treeview.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Directories under build/ that must NEVER be shown in the repository browser.
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
    "wrong-branch",
    "no-progress",
    "noop-clean",
    "editor-runtime",
}

# Explicit navigation-only metadata for tree organisation.
# This is explicitly NOT a canonical semantic truth source; it is a UI
# navigation layout helper that groups related probe and example diagrams.
NAVIGATION_METADATA: dict[str, dict[str, str]] = {
    "examples/loam-balance-probe/loam_balance_probe.drn": {
        "group": "LOAM probes",
        "section": "balance",
        "annotation": "→ retained sequence",
    },
    "examples/loam-bounded-changes-probe/array_fold.drn": {
        "group": "LOAM probes",
        "section": "bounded changes",
        "annotation": "→ active prefix",
    },
    "examples/loam-active-prefix-probe/active_prefix_fold.drn": {
        "group": "LOAM probes",
        "section": "active prefix",
        "annotation": "→ coordinate/quantity pairing",
    },
    "build/quantity-at-two/quantity_at_two.drn": {
        "group": "LOAM probes",
        "section": "quantityAt [working]",
        "annotation": "",
    },
    "examples/control-flow/branch/branch.drn": {
        "group": "Control flow",
        "section": "branch",
        "annotation": "",
    },
    "examples/control-flow/countdown/countdown.drn": {
        "group": "Control flow",
        "section": "countdown",
        "annotation": "",
    },
    "examples/movement/movement.drn": {
        "group": "Movement",
        "section": "movement",
        "annotation": "",
    },
}


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    cursor = db.execute(
        "select 1 from sqlite_master where type='table' and name=?", (name,)
    )
    return cursor.fetchone() is not None


from urllib.request import pathname2url

def inspect_drn_diagrams(path: Path) -> list[dict[str, Any]]:
    """Read diagram IDs and names from a .drn SQLite file in read-only mode."""
    uri = f"file:{pathname2url(str(path.resolve()))}?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        if not table_exists(db, "diagrams"):
            return []
        cursor = db.execute(
            "select diagram_id, name, description from diagrams order by diagram_id"
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        db.close()


def discover_canonical_files(root: Path) -> list[Path]:
    """Find all canonical .drn files under examples/."""
    examples_dir = root / "examples"
    if not examples_dir.is_dir():
        return []
    return sorted(examples_dir.rglob("*.drn"))


def discover_working_files(root: Path) -> list[Path]:
    """Find positive working .drn files under build/."""
    build_dir = root / "build"
    if not build_dir.is_dir():
        return []
    working: list[Path] = []
    for path in sorted(build_dir.rglob("*.drn")):
        parts = set(path.relative_to(build_dir).parts)
        if parts & SKIP_BUILD_PARTS:
            continue
        working.append(path)
    return working


def discover_all_drn_files(root: Path, include_build: bool = True) -> list[dict[str, Any]]:
    """Discover all eligible .drn files with their metadata and diagrams."""
    results: list[dict[str, Any]] = []

    for path in discover_canonical_files(root):
        rel = str(path.relative_to(root))
        diagrams = inspect_drn_diagrams(path)
        nav = NAVIGATION_METADATA.get(rel, {})
        results.append({
            "rel_path": rel,
            "abs_path": str(path.resolve()),
            "kind": "canonical",
            "group": nav.get("group", derive_group(rel)),
            "section": nav.get("section", derive_section(rel)),
            "annotation": nav.get("annotation", ""),
            "diagrams": diagrams,
        })

    if include_build:
        for path in discover_working_files(root):
            rel = str(path.relative_to(root))
            diagrams = inspect_drn_diagrams(path)
            nav = NAVIGATION_METADATA.get(rel, {})
            results.append({
                "rel_path": rel,
                "abs_path": str(path.resolve()),
                "kind": "working",
                "group": nav.get("group", derive_group(rel)),
                "section": nav.get("section", derive_section(rel)),
                "annotation": nav.get("annotation", ""),
                "diagrams": diagrams,
            })

    return results


def derive_group(rel_path: str) -> str:
    parts = Path(rel_path).parts
    if len(parts) > 1 and parts[0] == "examples":
        first = parts[1]
        if first.startswith("loam"):
            return "LOAM probes"
        if first == "control-flow":
            return "Control flow"
        return first.replace("-", " ").title()
    if len(parts) > 1 and parts[0] == "build":
        return "Build [working]"
    return "Repository"


def derive_section(rel_path: str) -> str:
    parts = Path(rel_path).parts
    if len(parts) > 2:
        return parts[-2].replace("-", " ")
    return Path(rel_path).stem.replace("-", " ")


def build_catalog_tree(root: Path, include_build: bool = True) -> dict[str, Any]:
    """Build a structured tree node list ready for ttk::treeview consumption."""
    discovered = discover_all_drn_files(root, include_build=include_build)

    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in discovered:
        grp = item["group"]
        sec = item["section"]
        groups.setdefault(grp, {}).setdefault(sec, []).append(item)

    # Order groups: "LOAM probes" first, then "Control flow", "Movement", others
    preferred_order = ["LOAM probes", "Control flow", "Movement"]
    all_group_names = sorted(
        groups.keys(),
        key=lambda g: (preferred_order.index(g) if g in preferred_order else 999, g),
    )

    preferred_section_order = {
        "LOAM probes": ["balance", "bounded changes", "active prefix", "quantityAt [working]"],
        "Control flow": ["branch", "countdown"],
    }

    nodes: list[dict[str, Any]] = []

    # Root node: "Drakon-ada"
    repo_node_id = "root:repo"
    nodes.append({
        "id": repo_node_id,
        "parent": "",
        "text": "Drakon-ada",
        "type": "root",
        "open": True,
    })

    for grp_name in all_group_names:
        grp_node_id = f"grp:{grp_name.replace(' ', '_').lower()}"
        nodes.append({
            "id": grp_node_id,
            "parent": repo_node_id,
            "text": grp_name,
            "type": "group",
            "open": True,
        })

        sections = groups[grp_name]
        sec_pref = preferred_section_order.get(grp_name, [])
        sorted_sec_names = sorted(
            sections.keys(),
            key=lambda s: (sec_pref.index(s) if s in sec_pref else 999, s),
        )
        for sec_name in sorted_sec_names:
            files = sections[sec_name]
            # If section has only 1 file and section name is non-empty,
            # section can host the file's diagrams directly or file nodes.
            # To strictly follow:
            # ├─ LOAM probes
            # │  ├─ balance
            # │  │  └─ Loam_Balance_Probe
            sec_node_id = f"sec:{grp_node_id}:{sec_name.replace(' ', '_').lower()}"
            first_annot = files[0]["annotation"] if files and files[0]["annotation"] else ""
            sec_text = f"{sec_name} {first_annot}".strip() if first_annot else sec_name

            nodes.append({
                "id": sec_node_id,
                "parent": grp_node_id,
                "text": sec_text,
                "type": "section",
                "open": True,
            })

            for f in files:
                rel = f["rel_path"]
                # If multiple files under section, add a file node
                file_node_id = f"file:{rel}"
                if len(files) > 1:
                    nodes.append({
                        "id": file_node_id,
                        "parent": sec_node_id,
                        "text": Path(rel).name,
                        "type": "file",
                        "rel_path": rel,
                        "abs_path": f["abs_path"],
                        "kind": f["kind"],
                        "open": True,
                    })
                    diagram_parent = file_node_id
                else:
                    diagram_parent = sec_node_id

                for dia in f["diagrams"]:
                    dia_id = dia["diagram_id"]
                    dia_name = dia["name"]
                    node_id = f"dia:{rel}:{dia_id}"
                    nodes.append({
                        "id": node_id,
                        "parent": diagram_parent,
                        "text": dia_name,
                        "type": "diagram",
                        "diagram_id": dia_id,
                        "rel_path": rel,
                        "abs_path": f["abs_path"],
                        "kind": f["kind"],
                    })

    return {
        "repository": "Drakon-ada",
        "root_path": str(root.resolve()),
        "nodes": nodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DRAKON Editor repository catalog generator")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root directory")
    parser.add_argument("--output", type=Path, help="Output JSON path")
    parser.add_argument("--no-build", action="store_true", help="Exclude positive build diagrams")
    args = parser.parse_args()

    catalog = build_catalog_tree(args.root, include_build=not args.no_build)
    raw = json.dumps(catalog, indent=2, ensure_ascii=False)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
        print(f"Wrote repository catalog ({len(catalog['nodes'])} nodes) to {args.output}")
    else:
        print(raw)


if __name__ == "__main__":
    main()
