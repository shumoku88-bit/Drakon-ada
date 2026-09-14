#!/usr/bin/env python3
"""Build the temporary Phase-A1 bounded-array DRAKON qualification fixture."""
from pathlib import Path
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "examples/control-flow/countdown/countdown.drn"

LOOP_INVARIANT = (
    "Index >= 1 and then Index <= 4 and then "
    "((Index = 1 and then Total = 0) or else "
    "(Index = 2 and then Total = Items (1)) or else "
    "(Index = 3 and then Total = Items (1) + Items (2)) or else "
    "(Index = 4 and then Total = Items (1) + Items (2) + Items (3)))"
)
WEAK_LOOP_INVARIANT = "Index >= 1 and then Index <= 4"

ARRAY_METADATA = f"""schema 3
profile SPARK
package Array_Fold
declarations {{{{integer Quantity -40 40}} {{subtype Change_Quantity Quantity -10 10}} {{integer Index_Type 1 5}} {{subtype Slot Index_Type 1 4}} {{array Change_Array Slot Change_Quantity}}}}
parameters {{{{Items in Change_Array}} {{Total out Quantity}}}}
locals {{{{Index Index_Type}}}}
post {{Total = Items (1) + Items (2) + Items (3) + Items (4)}}
loop_annotations {{9 {{invariant {{{LOOP_INVARIANT}}} variant {{Decreases {{5 - Index}}}}}}}}
always_terminates True"""

INIT_ACTION = "Index := 1;\nTotal := 0;"
FOLD_ACTION = "Total := Total + Items (Index);\nIndex := Index + 1;"

# Keep temporary fixture geometry derived from the pinned upstream editor rather
# than from probe-specific magic numbers. DRAKON Editor's headless unit-test
# window measures text at 6 units per character and 20 units per line, while
# action.fit uses measured width (with a minimum of 50) and measured height as
# the action icon's w/h fields. Production Tk font metrics are still checked by
# the human visual-review gate before this diagram can become canonical.
_UPSTREAM_TEST_CHAR_WIDTH = 6
_UPSTREAM_TEST_LINE_HEIGHT = 20
_UPSTREAM_ACTION_MIN_WIDTH = 50


def headless_action_fit(text: str) -> tuple[int, int]:
    """Return action w/h using the pinned upstream headless fit contract."""
    lines = text.split("\n")
    if not lines:
        lines = [""]
    text_width = max((len(line) * _UPSTREAM_TEST_CHAR_WIDTH for line in lines), default=0)
    text_height = _UPSTREAM_TEST_LINE_HEIGHT * max(1, len(lines))
    return max(_UPSTREAM_ACTION_MIN_WIDTH, text_width), text_height


def _rewrite_action(db: sqlite3.Connection, old_text: str, new_text: str) -> None:
    width, height = headless_action_fit(new_text)
    db.execute(
        "update items set text=?, w=?, h=? where type='action' and text=?",
        (new_text, width, height, old_text),
    )


def materialize(destination: Path) -> Path:
    """Copy the qualified countdown geometry and rewrite its semantic content."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATE, destination)
    with sqlite3.connect(destination) as db:
        db.execute("update diagrams set name='Fold_Four'")
        db.execute(
            "update items set text='Fold_Four' where type='beginend' and text='Count_Down'"
        )
        _rewrite_action(db, "Count := Amount;", INIT_ACTION)
        db.execute("update items set text='Index <= 4' where type='if'")
        _rewrite_action(db, "Count := Count - 1;", FOLD_ACTION)
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
