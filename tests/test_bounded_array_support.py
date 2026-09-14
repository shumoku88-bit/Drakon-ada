"""Qualify the smallest array/local surface before adding a canonical LOAM sequence diagram."""
from pathlib import Path
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

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


class BoundedArraySupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.source = self.work / "array_fold.drn"
        shutil.copyfile(TEMPLATE, self.source)
        self._rewrite_as_array_fold()

    def _rewrite_as_array_fold(self):
        with sqlite3.connect(self.source) as db:
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
            db.execute(
                "update diagram_info set value=? where name='ada'", (ARRAY_METADATA,)
            )
            db.commit()

    def generate(self, success=True):
        out = self.work / "generated"
        result = subprocess.run(
            [
                os.environ.get("TCLSH", "tclsh"),
                str(ROOT / "integration/drakon-editor/generate.tcl"),
                str(self.source),
                str(out),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return out, result

    def test_schema3_emits_only_the_earned_array_and_local_surface(self):
        out, _ = self.generate()
        spec = (out / "array_fold.ads").read_text()
        body = (out / "array_fold.adb").read_text()

        self.assertIn("type Change_Array is array (Slot) of Change_Quantity;", spec)
        self.assertIn("Items : in Change_Array; Total : out Quantity", spec)
        self.assertIn(
            "Post => Total = Items (1) + Items (2) + Items (3) + Items (4)", spec
        )
        self.assertIn("Index : Index_Type;", body)
        self.assertIn("Remaining : Remaining_Type;", body)
        self.assertIn("Total := Total + Items (Index);", body)
        self.assertIn("pragma Loop_Variant (Decreases => Remaining);", body)
        self.assertIn("Always_Terminates => True", spec)

    def test_non_array_call_syntax_remains_rejected(self):
        with sqlite3.connect(self.source) as db:
            db.execute(
                "update items set text=replace(text, 'Items (Index)', 'Fake (Index)') "
                "where type='action'"
            )
        _, result = self.generate(False)
        self.assertIn("Unsupported expression", result.stderr)

    def test_array_local_is_rejected(self):
        with sqlite3.connect(self.source) as db:
            value = db.execute(
                "select value from diagram_info where name='ada'"
            ).fetchone()[0]
            value = value.replace(
                "locals {{Index Index_Type} {Remaining Remaining_Type}}",
                "locals {{Index Index_Type} {Remaining Remaining_Type} {Scratch Change_Array}}",
            )
            db.execute("update diagram_info set value=? where name='ada'", (value,))
        _, result = self.generate(False)
        self.assertIn("Array locals are not supported", result.stderr)


if __name__ == "__main__":
    unittest.main()
