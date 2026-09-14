"""Bounded LOAM balance-admission dogfood; no LOAM code or household data."""
from pathlib import Path
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import materialize_loam_balance_probe as probe  # noqa: E402


class LoamBalanceProbeTests(unittest.TestCase):
    def setUp(self):
        self.template_digest = hashlib.sha256(probe.TEMPLATE.read_bytes()).digest()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.source = probe.materialize(self.work / "loam_balance_probe.drn")
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

    def test_materialization_preserves_checked_in_template(self):
        self.assertEqual(
            self.template_digest, hashlib.sha256(probe.TEMPLATE.read_bytes()).digest()
        )

    def test_materialized_semantic_shape_is_explicit(self):
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
        self.assertEqual(condition, "First + Second + Third = 0")
        self.assertEqual(actions, {probe.TRUE_ACTION, probe.FALSE_ACTION})
        self.assertEqual(metadata, probe.ADA_METADATA)

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
            db.execute(
                "update items set text='First + Second - Third = 0' where type='if'"
            )
        self.generate()
        body = (self.out / "loam_balance_admission.adb").read_text()
        spec = (self.out / "loam_balance_admission.ads").read_text()
        self.assertIn("if First + Second - Third = 0 then", body)
        self.assertIn(
            "Total = First + Second + Third and then Accepted = (Total = 0)", spec
        )


if __name__ == "__main__":
    unittest.main()
