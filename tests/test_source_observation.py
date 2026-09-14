"""Phase O2 normalized Ada/SPARK control-flow observation."""
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

    def test_fixture_emits_exact_normalized_control_flow(self):
        observation = json.loads(self.run_observer().stdout)

        self.assertEqual(
            observation["schema"], "drakon-ada/control-flow-observation/v1"
        )
        self.assertTrue(observation["complete"])
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
        self.assertEqual(observation["entry_node"], "entry")
        self.assertEqual(observation["exit_node"], "exit")

        nodes = observation["nodes"]
        self.assertEqual(
            [node["id"] for node in nodes],
            ["entry"] + [f"n{index:04d}" for index in range(1, 10)] + ["exit"],
        )
        self.assertEqual(nodes[0]["kind"], "entry")
        self.assertEqual(nodes[-1]["kind"], "exit")
        self.assertEqual(nodes[0]["origin"], "synthetic")
        self.assertEqual(nodes[-1]["origin"], "synthetic")

        source_nodes = [node for node in nodes if node["origin"] == "source"]
        self.assertEqual(
            [node["ada_kind"] for node in source_nodes],
            [
                "AssignStmt",
                "IfStmt",
                "AssignStmt",
                "WhileLoopStmt",
                "AssignStmt",
                "AssignStmt",
                "IfStmt",
                "ReturnStmt",
                "AssignStmt",
            ],
        )
        self.assertEqual(
            [node["kind"] for node in source_nodes],
            [
                "action",
                "decision",
                "action",
                "loop",
                "action",
                "action",
                "decision",
                "return",
                "action",
            ],
        )
        by_id = {node["id"]: node for node in nodes}
        self.assertEqual(by_id["n0002"]["label"], "Remaining < 0")
        self.assertEqual(by_id["n0004"]["label"], "Remaining > 0")
        self.assertEqual(by_id["n0007"]["label"], "Result = 0")

        expected_edges = {
            ("entry", "n0001", "next"),
            ("n0001", "n0002", "next"),
            ("n0002", "n0003", "true"),
            ("n0002", "n0004", "false"),
            ("n0003", "n0007", "next"),
            ("n0004", "n0005", "loop_body"),
            ("n0004", "n0007", "loop_exit"),
            ("n0005", "n0006", "next"),
            ("n0006", "n0004", "back"),
            ("n0007", "n0008", "true"),
            ("n0007", "n0009", "false"),
            ("n0008", "exit", "return"),
            ("n0009", "exit", "next"),
        }
        self.assertEqual(
            {(edge["from"], edge["to"], edge["role"]) for edge in observation["edges"]},
            expected_edges,
        )

        for node in source_nodes:
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

    def test_unqualified_control_flow_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsupported = root / "unsupported.adb"
            unsupported.write_text(
                """procedure Unsupported is
   X : Integer := 0;
begin
   case X is
      when others => null;
   end case;
end Unsupported;
"""
            )
            result = self.run_observer(unsupported, root, ok=False)
            self.assertIn("unsupported control-flow statement CaseStmt", result.stderr)

    def test_exception_handler_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsupported = root / "unsupported.adb"
            unsupported.write_text(
                """procedure Unsupported is
begin
   null;
exception
   when others => null;
end Unsupported;
"""
            )
            result = self.run_observer(unsupported, root, ok=False)
            self.assertIn("exception handlers are unsupported", result.stderr)


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
