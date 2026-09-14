"""Real DRAKON sources, normalized through upstream; no mocked trees."""
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ControlFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def source(self, name):
        path = self.work / f'{name}.drn'
        shutil.copyfile(ROOT / f'examples/control-flow/{name}/{name}.drn', path)
        return path

    def generate(self, source, success=True):
        out = self.work / source.stem
        result = subprocess.run([os.environ.get('TCLSH', 'tclsh'),
                                 str(ROOT / 'integration/drakon-editor/generate.tcl'),
                                 str(source), str(out)], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return out, result

    def mutate(self, source, sql, args=()):
        with sqlite3.connect(source) as db:
            db.execute(sql, args)

    def test_golden_repeatable_no_source_mutation(self):
        for name in ('branch', 'countdown'):
            with self.subTest(name=name):
                source = self.source(name)
                digest = hashlib.sha256(source.read_bytes()).digest()
                out, _ = self.generate(source)
                first = {p.name: p.read_bytes() for p in out.iterdir()}
                self.assertEqual(set(first), {name + '.ads', name + '.adb'})
                for file, data in first.items():
                    self.assertEqual(data, (ROOT / 'tests/golden/control-flow' / file).read_bytes())
                shutil.rmtree(out)
                self.generate(source)
                self.assertEqual(first, {p.name: p.read_bytes() for p in out.iterdir()})
                self.assertEqual(digest, hashlib.sha256(source.read_bytes()).digest())

    def test_ada_and_spark_share_control_flow(self):
        for name in ('branch', 'countdown'):
            source = self.source(name)
            self.mutate(source, "UPDATE info SET value='Ada' WHERE key='language'")
            self.mutate(source, "UPDATE diagram_info SET value=replace(value,'profile SPARK','profile Ada')")
            out, _ = self.generate(source)
            expected = (ROOT / f'tests/golden/control-flow/{name}.adb').read_text()
            self.assertEqual((out / f'{name}.adb').read_text(),
                             expected.replace(' with SPARK_Mode => On', ''))

    def test_annotation_outside_loop_is_rejected(self):
        source = self.source('countdown')
        self.mutate(source, "UPDATE diagram_info SET value=replace(value,'loop_annotations {9','loop_annotations {4')")
        _, result = self.generate(source, False)
        self.assertIn('not inside a normalized loop', result.stderr)

    def test_annotation_missing_icon_is_rejected(self):
        source = self.source('countdown')
        self.mutate(source, "UPDATE diagram_info SET value=replace(value,'loop_annotations {9','loop_annotations {999')")
        _, result = self.generate(source, False)
        self.assertIn('must be an action icon', result.stderr)

    def test_missing_explicit_variant_is_rejected(self):
        source = self.source('countdown')
        self.mutate(source, "UPDATE diagram_info SET value=replace(value,'variant {Decreases Count}','')")
        self.generate(source, False)

    def test_invariant_not_inferred_from_condition(self):
        source = self.source('countdown')
        self.mutate(source, "UPDATE diagram_info SET value=replace(value,'invariant {Count > 0 and then Count <= Amount}','invariant {Count <= Amount}')")
        out, _ = self.generate(source)
        self.assertIn('pragma Loop_Invariant (Count <= Amount);',
                      (out / 'countdown.adb').read_text())

    def test_contract_pragmas_cannot_be_injected(self):
        source = self.source('countdown')
        self.mutate(source, "UPDATE diagram_info SET value=replace(value,'invariant {Count > 0 and then Count <= Amount}','invariant {True); pragma Assume (True}')")
        self.generate(source, False)


if __name__ == '__main__':
    unittest.main()
