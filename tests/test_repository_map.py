"""Tests for the derived repository/DRAKON map."""

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/repository_map.py"


class RepositoryMapTests(unittest.TestCase):
    def run_map(self, *extra):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        result = subprocess.run(
            [sys.executable, str(TOOL), "--output-dir", str(out), *extra],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        return out, result.stdout

    def test_canonical_map_contains_qualified_sources_and_structure(self):
        out, stdout = self.run_map()
        model = json.loads((out / "repository-map.json").read_text())
        markdown = (out / "repository-map.md").read_text()

        self.assertEqual(model["schema"], 1)
        self.assertEqual(model["repository"]["name"], "Drakon-ada")
        self.assertIn("generator/ada.tcl", model["tracked_files"])

        by_source = {entry["source"]: entry for entry in model["drn_sources"]}
        expected = {
            "examples/control-flow/branch/branch.drn",
            "examples/control-flow/countdown/countdown.drn",
            "examples/loam-balance-probe/loam_balance_probe.drn",
            "examples/loam-bounded-changes-probe/array_fold.drn",
            "examples/loam-active-prefix-probe/active_prefix_fold.drn",
        }
        self.assertTrue(expected.issubset(by_source), sorted(by_source))
        self.assertTrue(all(by_source[path]["source_kind"] == "canonical" for path in expected))

        active = by_source["examples/loam-active-prefix-probe/active_prefix_fold.drn"]
        self.assertEqual(active["diagrams"][0]["name"], "Fold_Active_Prefix")
        self.assertEqual(active["diagrams"][0]["ada"]["schema"], "3")
        self.assertEqual(active["diagrams"][0]["ada"]["profile"], "SPARK")
        self.assertTrue(active["references"])

        self.assertIn("# Drakon-ada repository map", markdown)
        self.assertIn("`Fold_Active_Prefix`", markdown)
        self.assertIn("`Index <= Length`", markdown)
        self.assertIn("GUI screenshot is still the authority", markdown)
        self.assertIn("repository map:", stdout)

    def test_default_map_does_not_depend_on_build_tree(self):
        out, _ = self.run_map()
        model = json.loads((out / "repository-map.json").read_text())
        self.assertFalse(
            any(entry["source"].startswith("build/") for entry in model["drn_sources"])
        )


if __name__ == "__main__":
    unittest.main()
