#!/usr/bin/env python3
"""Build the temporary Phase-A1 bounded-array DRAKON qualification fixture."""
from pathlib import Path
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "examples/control-flow/countdown/countdown.drn"

ARRAY_METADATA = """schema 3
profile SPARK
package Array_Fold
declarations {{integer Quantity -40 40} {subtype Change_Quantity Quantity -10 10} {integer Index_Type 1 5} {subtype Slot Index_Type 1 4} {integer Remaining_Type 0 4} {array Change_Array Slot Change_Quantity}}
parameters {{Items in Change_Array} {Total out Quantity}}
locals {{Index Index_Type} {Remaining Remaining_Type}}
post {Total = Items (1) + Items (2) + Items (3) + Items (4)}
loop_annotations {9 {invariant {Index >= 1 and then Index <= 4 and then Remaining = 5 - Index and then ((Index = 1 and then Total = 0) or else (Index = 2 and then Total = Items (1)) or else (Index = 3 and then Total = Items (1) + Items (2)) or else (Index = 4 and then Total = Items (1) + Items (2) + Items (3)))} variant {Decreases Remaining}}}
always_terminates True"""

INIT_ACTION = "Index := 1;\nRemaining := 4;\nTotal := 0;"
FOLD_ACTION = "Total := Total + Items (Index);\nIndex := Index + 1;\nRemaining := Remaining - 1;"


def materialize(destination: Path) -> Path:
    """Copy the qualified countdown geometry and rewrite only its semantic content."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATE, destination)
    with sqlite3.connect(destination) as db:
        db.execute("update diagrams set name='Fold_Four'")
        db.execute(
            "update items set text='Fold_Four' where type='beginend' and text='Count_Down'"
        )
        db.execute(
            "update items set text=? where type='action' and text='Count := Amount;'",
            (INIT_ACTION,),
        )
        db.execute("update items set text='Index <= 4' where type='if'")
        db.execute(
            "update items set text=? where type='action' and text='Count := Count - 1;'",
            (FOLD_ACTION,),
        )
        db.execute("update diagram_info set value=? where name='ada'", (ARRAY_METADATA,))
        db.commit()
    return destination


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "destination",
        nargs="?",
        type=Path,
        default=ROOT / "build/bounded-array-support/array_fold.drn",
    )
    args = parser.parse_args()
    print(materialize(args.destination))
