#!/usr/bin/env python3
"""Materialize the temporary Phase-A2 active-prefix candidate from Phase A1."""
from pathlib import Path
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
PHASE_A1 = ROOT / "examples/loam-bounded-changes-probe/array_fold.drn"

INIT_ACTION = "Index := 1;\nTotal := 0;"
FOLD_ACTION = "Total := Total + Items (Index);\nIndex := Index + 1;"
CONDITION = "Index <= Length"

# Actual Mac Tk measurement for Menlo 14 used by the review Editor. Mirror the
# pinned p.measure_text -> if.fit transform only for this candidate decision.
_GUI_CONDITION_TEXT_WIDTH = 120
_GUI_CONDITION_TEXT_HEIGHT = 17
_GRID = 10
_FIT_PADDING = 10


def _snap_up(value: int) -> int:
    return ((value + _GRID - 1) // _GRID) * _GRID


def gui_condition_fit() -> tuple[int, int]:
    action_w = _snap_up(_GUI_CONDITION_TEXT_WIDTH // 2) + _FIT_PADDING
    action_h = _snap_up(_GUI_CONDITION_TEXT_HEIGHT // 2) + _FIT_PADDING
    return _snap_up(action_w + action_h // 2), action_h

PREFIX_CASES = (
    "(Length = 0 and then Total = 0) or else "
    "(Length = 1 and then Total = Items (1)) or else "
    "(Length = 2 and then Total = Items (1) + Items (2)) or else "
    "(Length = 3 and then Total = Items (1) + Items (2) + Items (3)) or else "
    "(Length = 4 and then Total = Items (1) + Items (2) + Items (3) + Items (4))"
)
LOOP_INVARIANT = (
    "Index >= 1 and then Index <= Length and then Index <= 4 and then "
    "((Index = 1 and then Total = 0) or else "
    "(Index = 2 and then Total = Items (1)) or else "
    "(Index = 3 and then Total = Items (1) + Items (2)) or else "
    "(Index = 4 and then Total = Items (1) + Items (2) + Items (3)))"
)
WEAK_LOOP_INVARIANT = "Index >= 1 and then Index <= Length"

ACTIVE_PREFIX_METADATA = f"""schema 3
profile SPARK
package Active_Prefix_Fold
declarations {{{{integer Quantity -40 40}} {{subtype Change_Quantity Quantity -10 10}} {{integer Index_Type 0 5}} {{subtype Slot Index_Type 1 4}} {{subtype Active_Length Index_Type 0 4}} {{array Change_Array Slot Change_Quantity}}}}
parameters {{{{Items in Change_Array}} {{Length in Active_Length}} {{Total out Quantity}}}}
locals {{{{Index Index_Type}}}}
post {{{PREFIX_CASES}}}
loop_annotations {{9 {{invariant {{{LOOP_INVARIANT}}} variant {{Decreases {{5 - Index}}}}}}}}
always_terminates True"""


def materialize(destination: Path) -> Path:
    """Copy Phase A1 and change only Phase-A2 identity, bound and metadata."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PHASE_A1, destination)
    with sqlite3.connect(destination) as db:
        db.execute(
            "update diagrams set name='Fold_Active_Prefix', "
            "description='Temporary Phase A2 active-prefix qualification'"
        )
        db.execute(
            "update items set text='Fold_Active_Prefix' "
            "where type='beginend' and text='Fold_Four'"
        )
        decision = db.execute(
            "select item_id,x,w,h,a from items where type='if'"
        ).fetchall()
        if len(decision) != 1:
            raise ValueError("Expected exactly one Phase A1 decision icon")
        item_id, x, old_w, old_h, old_a = decision[0]
        endpoint = x + old_w + old_a
        width, height = gui_condition_fit()
        if height != old_h:
            raise ValueError("Decision height change would require vertical reflow")
        branch = endpoint - x - width
        if branch < 20:
            raise ValueError("Fitted decision leaves no legal branch arm")
        db.execute(
            "update items set text=?,w=?,h=?,a=? where item_id=?",
            (CONDITION, width, height, branch, item_id),
        )
        db.execute(
            "update diagram_info set value=? where name='ada'",
            (ACTIVE_PREFIX_METADATA,),
        )
        db.commit()
    return destination


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "destination",
        nargs="?",
        type=Path,
        default=ROOT / "build/active-prefix-support/active_prefix_fold.drn",
    )
    args = parser.parse_args()
    print(materialize(args.destination))
