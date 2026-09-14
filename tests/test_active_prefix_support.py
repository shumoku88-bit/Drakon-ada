"""Focused tests for the canonical Phase-A2 active-prefix witness."""
from pathlib import Path
import hashlib
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SOURCE = ROOT / "examples/loam-active-prefix-probe/active_prefix_fold.drn"
PHASE_A1 = ROOT / "examples/loam-bounded-changes-probe/array_fold.drn"

INIT_ACTION = "Index := 1;\nTotal := 0;"
FOLD_ACTION = "Total := Total + Items (Index);\nIndex := Index + 1;"
CONDITION = "Index <= Length"
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
ACTIVE_PREFIX_METADATA = f"""schema 3
profile SPARK
package Active_Prefix_Fold
declarations {{{{integer Quantity -40 40}} {{subtype Change_Quantity Quantity -10 10}} {{integer Index_Type 0 5}} {{subtype Slot Index_Type 1 4}} {{subtype Active_Length Index_Type 0 4}} {{array Change_Array Slot Change_Quantity}}}}
parameters {{{{Items in Change_Array}} {{Length in Active_Length}} {{Total out Quantity}}}}
locals {{{{Index Index_Type}}}}
post {{{PREFIX_CASES}}}
loop_annotations {{9 {{invariant {{{LOOP_INVARIANT}}} variant {{Decreases {{5 - Index}}}}}}}}
always_terminates True"""


class ActivePrefixSupportTests(unittest.TestCase):
    def setUp(self):
        self.canonical_digest = hashlib.sha256(CANONICAL_SOURCE.read_bytes()).digest()
        self.phase_a1_digest = hashlib.sha256(PHASE_A1.read_bytes()).digest()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.source = self.work / "active_prefix_fold.drn"
        shutil.copyfile(CANONICAL_SOURCE, self.source)

    def generate(self):
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
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return out

    def test_existing_schema3_surface_emits_active_prefix(self):
        out = self.generate()
        spec = (out / "active_prefix_fold.ads").read_text()
        body = (out / "active_prefix_fold.adb").read_text()
        self.assertIn("subtype Active_Length is Index_Type range 0 .. 4;", spec)
        self.assertIn("Length : in Active_Length", spec)
        self.assertIn("if Index <= Length then", body)
        self.assertIn("pragma Loop_Variant (Decreases => 5 - Index);", body)
        self.assertIn("Length = 0 and then Total = 0", spec)
        self.assertIn(
            "Length = 4 and then Total = Items (1) + Items (2) + Items (3) + Items (4)",
            spec,
        )
        self.assertNotIn("Remaining", body)
        self.assertNotIn("Length :=", body)
        self.assertEqual(
            self.canonical_digest, hashlib.sha256(CANONICAL_SOURCE.read_bytes()).digest()
        )

    def test_canonical_semantics_are_explicit_and_phase_a1_is_unchanged(self):
        with sqlite3.connect(self.source) as db:
            name = db.execute("select name from diagrams").fetchone()[0]
            metadata = db.execute(
                "select value from diagram_info where name='ada'"
            ).fetchone()[0]
            condition = db.execute(
                "select text from items where type='if'"
            ).fetchone()[0]
            actions = {
                row[0] for row in db.execute("select text from items where type='action'")
            }
        self.assertEqual(name, "Fold_Active_Prefix")
        self.assertEqual(metadata, ACTIVE_PREFIX_METADATA)
        self.assertEqual(condition, CONDITION)
        self.assertEqual(actions, {INIT_ACTION, FOLD_ACTION})
        self.assertEqual(
            self.phase_a1_digest, hashlib.sha256(PHASE_A1.read_bytes()).digest()
        )

    def test_canonical_gui_geometry_has_clearance_and_connected_graph(self):
        with sqlite3.connect(self.source) as db:
            fold = db.execute(
                "select x,y,w,h from items where type='action' and text=?",
                (FOLD_ACTION,),
            ).fetchone()
            trunk = db.execute(
                "select x from items where type='vertical' order by x limit 1"
            ).fetchone()[0]
            loopback = db.execute(
                "select x from items where type='arrow'"
            ).fetchone()[0]
            decision = db.execute(
                "select x,y,w,h,a from items where type='if'"
            ).fetchone()
        self.assertEqual(decision, (180, 240, 80, 20, 70))
        self.assertEqual(decision[0] + decision[2] + decision[4], fold[0])
        self.assertEqual(fold, (330, 300, 140, 30))
        self.assertEqual((trunk, loopback), (180, 480))
        self.assertEqual(fold[0] - fold[2] - trunk, 10)
        self.assertEqual(loopback - (fold[0] + fold[2]), 10)
        self.generate()  # Includes upstream graph verification.


if __name__ == "__main__":
    unittest.main()
