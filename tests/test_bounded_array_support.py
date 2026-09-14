"""Qualify the canonical Phase-A1 bounded retained-sequence witness."""
from pathlib import Path
import hashlib
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SOURCE = (
    ROOT / "examples/loam-bounded-changes-probe/array_fold.drn"
)

INIT_ACTION = "Index := 1;\nTotal := 0;"
FOLD_ACTION = "Total := Total + Items (Index);\nIndex := Index + 1;"


def headless_action_fit(text: str) -> tuple[int, int]:
    """Pinned dummy metric -> p.measure_text -> action.fit regression."""
    lines = text.split("\n") or [""]
    measured_width = max((len(line) * 6 for line in lines), default=0)
    measured_height = 20 * max(1, len(lines))
    snap_up = lambda value: ((value + 9) // 10) * 10
    return max(50, snap_up(measured_width // 2) + 10), snap_up(
        measured_height // 2
    ) + 10


class BoundedArraySupportTests(unittest.TestCase):
    def setUp(self):
        self.source_digest = hashlib.sha256(CANONICAL_SOURCE.read_bytes()).digest()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.source = self.work / "array_fold.drn"
        shutil.copyfile(CANONICAL_SOURCE, self.source)

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
        self.assertEqual(
            self.source_digest, hashlib.sha256(CANONICAL_SOURCE.read_bytes()).digest()
        )

    def test_headless_fit_is_not_the_canonical_gui_geometry(self):
        self.assertEqual(headless_action_fit(INIT_ACTION), (50, 30))
        self.assertEqual(headless_action_fit(FOLD_ACTION), (110, 30))

        with sqlite3.connect(self.source) as db:
            rows = db.execute(
                "select text, w, h from items where type='action'"
            ).fetchall()
        geometry = {text: (width, height) for text, width, height in rows}
        self.assertEqual(geometry[INIT_ACTION], (60, 30))
        self.assertEqual(geometry[FOLD_ACTION], (140, 30))

    def test_canonical_fold_has_clearance_and_connected_graph(self):
        with sqlite3.connect(self.source) as db:
            x, y, w, h = db.execute(
                "select x, y, w, h from items where type='action' and text=?",
                (FOLD_ACTION,),
            ).fetchone()
            verticals = db.execute(
                "select x, y, h from items where type='vertical'"
            ).fetchall()
            ax, ay, aw, ah, aa = db.execute(
                "select x, y, w, h, a from items where type='arrow'"
            ).fetchone()
            bx, by, bw, ba = db.execute(
                "select x, y, w, a from items where type='if'"
            ).fetchone()
            coords = db.execute("select x, y, w, h, a from items").fetchall()

        self.assertEqual((x, y, w, h), (330, 300, 140, 30))
        self.assertTrue(all(value % 10 == 0 for row in coords for value in row))
        lanes = verticals + [(ax, ay, ah)]
        adjacent = [
            lx for lx, ly, lh in lanes
            if lx != x and ly < y + h and ly + lh > y - h
        ]
        self.assertEqual(len(adjacent), 2)
        self.assertEqual(x - w - max(lx for lx in adjacent if lx < x), 10)
        self.assertEqual(min(lx for lx in adjacent if lx > x) - (x + w), 10)
        self.assertEqual(bx + bw + ba, x)
        self.assertEqual(ax - aw, bx)
        self.assertEqual(ax - aa, x)
        self.assertIn((x, by, ay + ah - by), verticals)
        self.generate()  # Includes upstream graph verification before Ada generation.

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
