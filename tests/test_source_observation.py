"""Phase O1 Ada/SPARK source observation probe."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/source-observation/observation_fixture.adb"
TOOL = ROOT / "tools/observe_ada.py"
HAS_LIBADALANG = importlib.util.find_spec("libadalang") is not None


@unittest.skipUnless(HAS_LIBADALANG, "Libadalang Python bindings are not installed")
class SourceObservationTests(unittest.TestCase):
    def run_observer(self, source=SOURCE, source_root=ROOT, ok=True):
        result = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                str(source),
                "--source-root",
                str(source_root),
            ],
            text=True,
            capture_output=True,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_fixture_is_observed_with_exact_source_identity(self):
        result = self.run_observer()
        observation = json.loads(result.stdout)

        self.assertEqual(observation["schema"], "drakon-ada/source-observation/v1")
        self.assertEqual(observation["frontend"]["name"], "libadalang")
        self.assertEqual(
            observation["source"]["path"],
            "examples/source-observation/observation_fixture.adb",
        )
        self.assertEqual(
            observation["source"]["sha256"],
            hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        )
        self.assertEqual(observation["subprogram"]["name"], "Observation_Fixture")

        nodes = observation["nodes"]
        self.assertTrue(nodes)
        self.assertEqual(
            [node["id"] for node in nodes],
            [f"n{index:04d}" for index in range(1, len(nodes) + 1)],
        )
        self.assertIn("decision", {node["kind"] for node in nodes})
        self.assertIn("loop", {node["kind"] for node in nodes})
        self.assertIn("return", {node["kind"] for node in nodes})
        self.assertIn("action", {node["kind"] for node in nodes})
        self.assertEqual(
            [node["ada_kind"] for node in nodes].count("IfStmt"), 2
        )
        self.assertEqual(
            [node["ada_kind"] for node in nodes].count("WhileLoopStmt"), 1
        )
        self.assertEqual(
            [node["ada_kind"] for node in nodes].count("ReturnStmt"), 1
        )

        for node in nodes:
            start = node["span"]["start"]
            end = node["span"]["end"]
            self.assertGreaterEqual(start["line"], 1)
            self.assertGreaterEqual(start["column"], 1)
            self.assertGreaterEqual(end["line"], start["line"])
            self.assertTrue(node["text"].strip())

    def test_observation_is_byte_for_byte_deterministic(self):
        first = self.run_observer().stdout
        second = self.run_observer().stdout
        self.assertEqual(first, second)

    def test_parse_diagnostics_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            broken = root / "broken.adb"
            broken.write_text("procedure Broken is begin if then end Broken;\n")
            result = self.run_observer(broken, root, ok=False)
            self.assertIn("Libadalang diagnostics", result.stderr)


class SourceObservationBoundaryTests(unittest.TestCase):
    def test_source_outside_root_is_rejected_before_frontend_use(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            source = Path(left) / "tiny.adb"
            source.write_text("procedure Tiny is begin null; end Tiny;\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    str(source),
                    "--source-root",
                    right,
                ],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside --source-root", result.stderr)


if __name__ == "__main__":
    unittest.main()
