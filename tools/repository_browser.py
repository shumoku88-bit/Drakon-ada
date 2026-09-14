#!/usr/bin/env python3
"""Repository discovery and navigation catalog generator for DRAKON Editor.

Discovers canonical DRAKON sources under ``examples/`` and positive working
copies under ``build/``, extracting diagram names and metadata for the
in-editor Repository Browser treeview.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
from typing import Any
from urllib.request import pathname2url

ROOT = Path(__file__).resolve().parents[1]

# Semantic & navigation metadata for repository probes.
# Keyed by diagram name so navigation does not permanently depend on transient
# build-directory paths and aligns seamlessly with future canonical promotion.
PROBE_SPECS: dict[str, dict[str, Any]] = {
    "Admit_Three_Changes": {
        "group": "LOAM probes",
        "section": "balance",
        "annotation": "→ retained sequence",
    },
    "Fold_Four": {
        "group": "LOAM probes",
        "section": "bounded changes",
        "annotation": "→ active prefix",
    },
    "Fold_Active_Prefix": {
        "group": "LOAM probes",
        "section": "active prefix",
        "annotation": "→ coordinate/quantity pairing",
    },
    "Quantity_At_Two": {
        "group": "LOAM probes",
        "section": "quantityAt",
        "annotation": "",
        # Working candidate priority order when no canonical source exists yet.
        # Prefers human-approved noop-clean over uncleaned scratch copies.
        "working_candidates": [
            "build/quantity-at-two/noop-clean/quantity_at_two.drn",
            "build/quantity-at-two/quantity_at_two.drn",
        ],
    },
    "Absolute_Value": {
        "group": "Control flow",
        "section": "branch",
        "annotation": "",
    },
    "Count_Down": {
        "group": "Control flow",
        "section": "countdown",
        "annotation": "",
    },
    "Balanced_Movement": {
        "group": "Movement",
        "section": "movement",
        "annotation": "",
    },
}

PREFERRED_GROUP_ORDER = ["LOAM probes", "Control flow", "Movement"]
PREFERRED_SECTION_ORDER = {
    "LOAM probes": ["balance", "bounded changes", "active prefix", "quantityAt [working]"],
    "Control flow": ["branch", "countdown"],
}


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    cursor = db.execute(
        "select 1 from sqlite_master where type='table' and name=?", (name,)
    )
    return cursor.fetchone() is not None


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


def discover_working_files(root: Path, canonical_diagram_names: set[str]) -> list[Path]:
    """Find active working copies under build/ that have not yet been promoted to canonical."""
    working: list[Path] = []

    # Check registered working candidates whose diagrams are not yet in canonical
    for dia_name, spec in PROBE_SPECS.items():
        if dia_name in canonical_diagram_names:
            continue
        for rel_cand in spec.get("working_candidates", []):
            cand_path = root / rel_cand
            if cand_path.is_file():
                working.append(cand_path)
                break  # Pick highest-priority existing candidate only

    return working


def discover_all_drn_files(root: Path, include_build: bool = True) -> list[dict[str, Any]]:
    """Discover all eligible .drn files with their resolved metadata and diagrams."""
    results: list[dict[str, Any]] = []
    seen_diagram_names: set[str] = set()

    # 1. Canonical files under examples/ (highest priority)
    for path in discover_canonical_files(root):
        rel = str(path.relative_to(root))
        diagrams = inspect_drn_diagrams(path)
        for dia in diagrams:
            seen_diagram_names.add(dia["name"])

        first_name = diagrams[0]["name"] if diagrams else ""
        spec = PROBE_SPECS.get(first_name, {})

        results.append({
            "rel_path": rel,
            "abs_path": str(path.resolve()),
            "kind": "canonical",
            "group": spec.get("group") or derive_group(rel),
            "section": spec.get("section") or derive_section(rel),
            "annotation": spec.get("annotation", ""),
            "diagrams": diagrams,
        })

    # 2. Working files under build/ (only those not yet promoted)
    if include_build:
        for path in discover_working_files(root, seen_diagram_names):
            rel = str(path.relative_to(root))
            diagrams = inspect_drn_diagrams(path)
            first_name = diagrams[0]["name"] if diagrams else ""
            spec = PROBE_SPECS.get(first_name, {})

            base_section = spec.get("section") or derive_section(rel)
            section = f"{base_section} [working]" if not base_section.endswith("[working]") else base_section

            results.append({
                "rel_path": rel,
                "abs_path": str(path.resolve()),
                "kind": "working",
                "group": spec.get("group") or "Build [working]",
                "section": section,
                "annotation": spec.get("annotation", ""),
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

    all_group_names = sorted(
        groups.keys(),
        key=lambda g: (PREFERRED_GROUP_ORDER.index(g) if g in PREFERRED_GROUP_ORDER else 999, g),
    )

    nodes: list[dict[str, Any]] = []

    # Root repository node
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
        sec_pref = PREFERRED_SECTION_ORDER.get(grp_name, [])
        sorted_sec_names = sorted(
            sections.keys(),
            key=lambda s: (sec_pref.index(s) if s in sec_pref else 999, s),
        )

        for sec_name in sorted_sec_names:
            files = sections[sec_name]
            sec_node_id = f"sec:{grp_node_id}:{sec_name.replace(' ', '_').lower()}"
            annot = files[0].get("annotation", "") if files else ""
            sec_text = f"{sec_name} {annot}".strip() if annot else sec_name

            nodes.append({
                "id": sec_node_id,
                "parent": grp_node_id,
                "text": sec_text,
                "type": "section",
                "open": True,
            })

            for f in files:
                rel = f["rel_path"]
                if len(files) > 1:
                    file_node_id = f"file:{rel}"
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
                    nodes.append({
                        "id": f"dia:{rel}:{dia_id}",
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
