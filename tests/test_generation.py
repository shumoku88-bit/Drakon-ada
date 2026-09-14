"""Only synthetic DRAKON inputs. No household data or LOAM dependency."""
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'examples/movement/movement.drn'


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.source = self.work / 'movement.drn'
        shutil.copyfile(SOURCE, self.source)
        self.out = self.work / 'generated'

    def sql(self, query, args=()):
        with sqlite3.connect(self.source) as db:
            db.execute(query, args)

    def generate(self, ok=True):
        result = subprocess.run(
            [os.environ.get('TCLSH', 'tclsh'),
             str(ROOT / 'integration/drakon-editor/generate.tcl'),
             str(self.source), str(self.out)], text=True, capture_output=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def metadata_replace(self, old, new):
        self.sql("UPDATE diagram_info SET value = replace(value, ?, ?) WHERE name = 'ada'", (old, new))

    def test_golden_and_repeatable_without_source_mutation(self):
        before = hashlib.sha256(self.source.read_bytes()).digest()
        self.generate()
        first = {p.name: p.read_bytes() for p in self.out.iterdir()}
        for name, content in first.items():
            self.assertEqual(content, (ROOT / 'tests/golden' / name).read_bytes())
        self.assertEqual(set(first), {'movement.ads', 'movement.adb'})
        shutil.rmtree(self.out)
        self.generate()
        self.assertEqual(first, {p.name: p.read_bytes() for p in self.out.iterdir()})
        self.assertEqual(before, hashlib.sha256(self.source.read_bytes()).digest())

    def test_control_flow_source_drives_body_not_contract(self):
        self.sql("UPDATE items SET text = 'Source := Amount;' WHERE item_id = 4")
        self.generate()
        self.assertIn('Source := Amount;', (self.out / 'movement.adb').read_text())
        self.assertIn('Source = -Amount', (self.out / 'movement.ads').read_text())

    def test_contract_is_explicit_not_inferred(self):
        self.metadata_replace('Source + Destination = 0', 'Source + Destination = 1')
        self.generate()
        self.assertIn('Source + Destination = 1', (self.out / 'movement.ads').read_text())
        self.assertEqual((self.out / 'movement.adb').read_bytes(),
                         (ROOT / 'tests/golden/movement.adb').read_bytes())

    def test_missing_contract_is_error(self):
        self.sql("DELETE FROM diagram_info WHERE name = 'ada'")
        self.assertIn('Missing explicit ada metadata', self.generate(False).stderr)
        self.assertFalse((self.out / 'movement.ads').exists())

    def test_profile_mismatch_is_error(self):
        self.sql("UPDATE info SET value = 'Ada' WHERE key = 'language'")
        self.assertIn('Language/profile mismatch', self.generate(False).stderr)

    def test_ada_profile_uses_same_body(self):
        self.sql("UPDATE info SET value = 'Ada' WHERE key = 'language'")
        self.metadata_replace('profile SPARK', 'profile Ada')
        self.generate()
        for name in ('movement.ads', 'movement.adb'):
            self.assertEqual((self.out / name).read_text(),
                             (ROOT / 'tests/golden' / name).read_text().replace(' with SPARK_Mode => On', ''))

    def test_broken_diagram_is_error(self):
        self.sql('DELETE FROM items WHERE item_id = 2')
        self.generate(False)
        self.assertFalse((self.out / 'movement.ads').exists())

    def test_hidden_control_and_proof_bypasses_are_rejected(self):
        for text in ('goto Earlier_Label;', 'pragma Assume (True);',
                     'pragma Suppress (All_Checks);', 'Source := Amount; goto L;',
                     'Source := F (Amount);'):
            with self.subTest(text=text):
                self.sql('UPDATE items SET text = ? WHERE item_id = 4', (text,))
                self.generate(False)

    def test_metadata_is_not_executed(self):
        self.metadata_replace('Source + Destination = 0', '[error injected]')
        result = self.generate(False)
        self.assertIn('Unsupported expression', result.stderr)


if __name__ == '__main__':
    unittest.main()
