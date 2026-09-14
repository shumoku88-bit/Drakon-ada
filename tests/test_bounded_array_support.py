"""Qualify the smallest array/local surface before adding a canonical LOAM sequence diagram."""
from pathlib import Path
import os
import sqlite3
import subprocess
import tempfile
import unittest

from tools.bounded_array_fixture import materialize

ROOT = Path(__file__).resolve().parents[1]


class BoundedArraySupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.source = materialize(self.work / "array_fold.drn")

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
        self.assertNotIn("Remaining", body)
        self.assertIn("Total := Total + Items (Index);", body)
        self.assertIn("pragma Loop_Variant (Decreases => 5 - Index);", body)
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
                "locals {{Index Index_Type}}",
                "locals {{Index Index_Type} {Scratch Change_Array}}",
            )
            db.execute("update diagram_info set value=? where name='ada'", (value,))
        _, result = self.generate(False)
        self.assertIn("Array locals are not supported", result.stderr)

    def test_variant_rejects_array_indexing(self):
        with sqlite3.connect(self.source) as db:
            value = db.execute(
                "select value from diagram_info where name='ada'"
            ).fetchone()[0]
            value = value.replace(
                "variant {Decreases {5 - Index}}",
                "variant {Decreases {Items (Index)}}",
            )
            db.execute("update diagram_info set value=? where name='ada'", (value,))
        _, result = self.generate(False)
        self.assertIn("Unsupported expression", result.stderr)

    def test_variant_rejects_function_call(self):
        with sqlite3.connect(self.source) as db:
            value = db.execute(
                "select value from diagram_info where name='ada'"
            ).fetchone()[0]
            value = value.replace(
                "variant {Decreases {5 - Index}}",
                "variant {Decreases {Fake_Func (Index)}}",
            )
            db.execute("update diagram_info set value=? where name='ada'", (value,))
        _, result = self.generate(False)
        self.assertIn("Unsupported expression", result.stderr)


if __name__ == "__main__":
    unittest.main()
