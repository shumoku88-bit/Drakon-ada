#!/usr/bin/env python3
"""Materialize a disposable LOAM balance-admission DRAKON probe.

This is deliberately a dogfood probe, not a LOAM migration. It reuses the
checked-in synthetic branch diagram as a geometry/control-flow template and
changes only the diagram name/start label, condition/actions, and explicit Ada
metadata. The resulting .drn lives under build/ and is not yet a new canonical
source.
"""
from pathlib import Path
import argparse
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "examples/control-flow/branch/branch.drn"
DEFAULT_OUTPUT = ROOT / "build/loam-balance-probe/loam_balance_probe.drn"

ADA_METADATA = (
    "schema 1 "
    "profile SPARK "
    "package Loam_Balance_Admission "
    "declarations {{integer Quantity -30 30} "
    "{subtype Change_Quantity Quantity -10 10}} "
    "parameters {{First in Change_Quantity} {Second in Change_Quantity} "
    "{Third in Change_Quantity} {Accepted out Boolean}} "
    "post {Accepted = (First + Second + Third = 0)}"
)


def _one(rows, label):
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one {label}, found {len(rows)}")
    return rows[0]


def materialize(output: Path) -> Path:
    output = Path(output)
    if not TEMPLATE.exists():
        raise RuntimeError(f"Missing checked-in branch template: {TEMPLATE}")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATE, output)

    with sqlite3.connect(output) as db:
        diagrams = db.execute("select diagram_id, name from diagrams").fetchall()
        diagram_id, diagram_name = _one(diagrams, "diagram")
        if diagram_name != "Absolute_Value":
            raise RuntimeError(f"Unexpected branch template diagram: {diagram_name!r}")

        starts = db.execute(
            "select item_id, text from items where diagram_id=? and type='beginend' and text='Absolute_Value'",
            (diagram_id,),
        ).fetchall()
        start_id, _ = _one(starts, "branch-template start icon")

        if_rows = db.execute(
            "select item_id, text from items where diagram_id=? and type='if'",
            (diagram_id,),
        ).fetchall()
        if_id, if_text = _one(if_rows, "if icon")
        if if_text != "Input >= 0":
            raise RuntimeError(f"Unexpected branch template condition: {if_text!r}")

        actions = db.execute(
            "select item_id, text from items where diagram_id=? and type='action'",
            (diagram_id,),
        ).fetchall()
        action_by_text = {text: item_id for item_id, text in actions}
        expected_actions = {"Result := Input;", "Result := -Input;"}
        if set(action_by_text) != expected_actions:
            raise RuntimeError(
                "Unexpected branch template actions: "
                + ", ".join(sorted(repr(text) for text in action_by_text))
            )

        db.execute(
            "update diagrams set name=?, description=? where diagram_id=?",
            (
                "Admit_Three_Changes",
                "LOAM-inspired bounded witness: admit exactly when three signed changes sum to zero.",
                diagram_id,
            ),
        )
        db.execute(
            "update items set text=? where item_id=?",
            ("Admit_Three_Changes", start_id),
        )
        db.execute(
            "update items set text=? where item_id=?",
            ("First + Second + Third = 0", if_id),
        )
        db.execute(
            "update items set text=? where item_id=?",
            ("Accepted := True;", action_by_text["Result := Input;"]),
        )
        db.execute(
            "update items set text=? where item_id=?",
            ("Accepted := False;", action_by_text["Result := -Input;"]),
        )
        db.execute(
            "update diagram_info set value=? where diagram_id=? and name='ada'",
            (ADA_METADATA, diagram_id),
        )
        if db.total_changes != 6:
            raise RuntimeError(
                f"Expected six semantic updates, observed {db.total_changes}; template drift?"
            )
        db.execute("update info set value='SPARK' where key='language'")
        db.commit()

        name = db.execute(
            "select name from diagrams where diagram_id=?", (diagram_id,)
        ).fetchone()[0]
        begin_labels = {
            row[0]
            for row in db.execute(
                "select text from items where diagram_id=? and type='beginend'", (diagram_id,)
            )
        }
        condition = db.execute(
            "select text from items where item_id=?", (if_id,)
        ).fetchone()[0]
        materialized_actions = {
            row[0]
            for row in db.execute(
                "select text from items where diagram_id=? and type='action'", (diagram_id,)
            )
        }
        metadata = db.execute(
            "select value from diagram_info where diagram_id=? and name='ada'",
            (diagram_id,),
        ).fetchone()[0]
        language = db.execute("select value from info where key='language'").fetchone()[0]

    if name != "Admit_Three_Changes":
        raise RuntimeError("Materialized procedure name mismatch")
    if "Admit_Three_Changes" not in begin_labels or "Absolute_Value" in begin_labels:
        raise RuntimeError("Materialized start label still carries branch-template semantics")
    if condition != "First + Second + Third = 0":
        raise RuntimeError("Materialized admission condition mismatch")
    if materialized_actions != {"Accepted := True;", "Accepted := False;"}:
        raise RuntimeError("Materialized admission branches mismatch")
    if metadata != ADA_METADATA or language != "SPARK":
        raise RuntimeError("Materialized explicit metadata/profile mismatch")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(materialize(args.output))


if __name__ == "__main__":
    main()
