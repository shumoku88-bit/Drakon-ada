"""Bounded LOAM balance-admission dogfood; canonical DRAKON source tests."""
from pathlib import Path
import hashlib
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SOURCE = ROOT / "examples/loam-balance-probe/loam_balance_probe.drn"

ADA_METADATA = (
    "schema 1\n"
    "profile SPARK\n"
    "package Loam_Balance_Admission\n"
    "declarations {{integer Quantity -30 30} {subtype Change_Quantity Quantity -10 10}}\n"
    "parameters {{First in Change_Quantity} {Second in Change_Quantity} "
    "{Third in Change_Quantity} {Total out Quantity} {Accepted out Boolean}}\n"
    "post {Total = First + Second + Third and then Accepted = (Total = 0)}"
)


class LoamBalanceProbeTests(unittest.TestCase):
    def setUp(self):
        self.source_digest = hashlib.sha256(CANONICAL_SOURCE.read_bytes()).digest()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.source = self.work / "loam_balance_probe.drn"
        shutil.copyfile(CANONICAL_SOURCE, self.source)
        self.out = self.work / "generated"

    def generate(self, ok=True):
        result = subprocess.run(
            [
                os.environ.get("TCLSH", "tclsh"),
                str(ROOT / "integration/drakon-editor/generate.tcl"),
                str(self.source),
                str(self.out),
            ],
            text=True,
            capture_output=True,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_canonical_source_not_mutated_by_generation(self):
        self.generate()
        self.assertEqual(
            self.source_digest, hashlib.sha256(CANONICAL_SOURCE.read_bytes()).digest()
        )

    def test_canonical_semantic_shape_is_explicit(self):
        with sqlite3.connect(self.source) as db:
            name = db.execute("select name from diagrams").fetchone()[0]
            begin_labels = {
                row[0] for row in db.execute("select text from items where type='beginend'")
            }
            condition = db.execute(
                "select text from items where type='if'"
            ).fetchone()[0]
            actions = {
                row[0] for row in db.execute("select text from items where type='action'")
            }
            metadata = db.execute(
                "select value from diagram_info where name='ada'"
            ).fetchone()[0]
        self.assertEqual(name, "Admit_Three_Changes")
        self.assertIn("Admit_Three_Changes", begin_labels)
        self.assertNotIn("Absolute_Value", begin_labels)
        self.assertEqual(condition, "Total = 0")
        self.assertEqual(
            actions,
            {
                "Total := First + Second + Third;",
                "Accepted := True;",
                "Accepted := False;",
            },
        )
        self.assertEqual(metadata, ADA_METADATA)

    def test_generation_matches_bounded_probe_golden(self):
        self.generate()
        generated = {p.name: p.read_bytes() for p in self.out.iterdir()}
        golden_dir = ROOT / "tests/golden/loam-balance-probe"
        self.assertEqual(
            set(generated), {"loam_balance_admission.ads", "loam_balance_admission.adb"}
        )
        for name, content in generated.items():
            self.assertEqual(content, (golden_dir / name).read_bytes())

    def test_control_flow_change_does_not_rewrite_contract(self):
        with sqlite3.connect(self.source) as db:
            db.execute("update items set text='Total = 1' where type='if'")
        self.generate()
        body = (self.out / "loam_balance_admission.adb").read_text()
        spec = (self.out / "loam_balance_admission.ads").read_text()
        self.assertIn("if Total = 1 then", body)
        self.assertIn(
            "Total = First + Second + Third and then Accepted = (Total = 0)", spec
        )


if __name__ == "__main__":
    unittest.main()
