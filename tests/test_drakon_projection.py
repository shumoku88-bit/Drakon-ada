"""Phase O3a deterministic DRAKON projection from normalized control flow."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/project_drakon.py"

SPEC = importlib.util.spec_from_file_location("project_drakon", TOOL)
assert SPEC is not None and SPEC.loader is not None
PROJECT_DRAKON = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROJECT_DRAKON)


def source_node(node_id, kind, text, ada_kind, label=None):
    node = {
        "id": node_id,
        "kind": kind,
        "origin": "source",
        "ada_kind": ada_kind,
        "text": text,
        "span": {
            "start": {"line": 1, "column": 1},
            "end": {"line": 1, "column": max(2, len(text) + 1)},
        },
    }
    if label is not None:
        node["label"] = label
    return node


def observation_fixture():
    nodes = [
        {"id": "entry", "kind": "entry", "origin": "synthetic"},
        source_node("n0001", "action", "Result := Remaining;", "AssignStmt"),
        source_node(
            "n0002",
            "decision",
            "if Remaining < 0 then",
            "IfStmt",
            "Remaining < 0",
        ),
        source_node("n0003", "action", "Result := -Remaining;", "AssignStmt"),
        source_node(
            "n0004",
            "loop",
            "while Remaining > 0 loop",
            "WhileLoopStmt",
            "Remaining > 0",
        ),
        source_node("n0005", "action", "Result := Result + 1;", "AssignStmt"),
        source_node("n0006", "action", "Remaining := Remaining - 1;", "AssignStmt"),
        source_node(
            "n0007",
            "decision",
            "if Result = 0 then",
            "IfStmt",
            "Result = 0",
        ),
        source_node("n0008", "return", "return;", "ReturnStmt"),
        source_node("n0009", "action", "Result := Result + 2;", "AssignStmt"),
        {"id": "exit", "kind": "exit", "origin": "synthetic"},
    ]
    edges = [
        {"from": "entry", "to": "n0001", "role": "next"},
        {"from": "n0001", "to": "n0002", "role": "next"},
        {"from": "n0002", "to": "n0003", "role": "true"},
        {"from": "n0002", "to": "n0004", "role": "false"},
        {"from": "n0003", "to": "n0007", "role": "next"},
        {"from": "n0004", "to": "n0005", "role": "loop_body"},
        {"from": "n0004", "to": "n0007", "role": "loop_exit"},
        {"from": "n0005", "to": "n0006", "role": "next"},
        {"from": "n0006", "to": "n0004", "role": "back"},
        {"from": "n0007", "to": "n0008", "role": "true"},
        {"from": "n0007", "to": "n0009", "role": "false"},
        {"from": "n0008", "to": "exit", "role": "return"},
        {"from": "n0009", "to": "exit", "role": "next"},
    ]
    return {
        "schema": "drakon-ada/control-flow-observation/v1",
        "complete": True,
        "frontend": {"name": "libadalang", "version": "26.0.0"},
        "source": {
            "path": "examples/source-observation/observation_fixture.adb",
            "sha256": "0" * 64,
        },
        "subprogram": {"name": "Observation_Fixture"},
        "entry_node": "entry",
        "exit_node": "exit",
        "nodes": nodes,
        "edges": edges,
    }


class DrakonProjectionTests(unittest.TestCase):
    def test_fixture_projects_exact_icons_roles_and_lanes(self):
        projection = PROJECT_DRAKON.project_observation(observation_fixture())

        self.assertEqual(projection["schema"], "drakon-ada/drakon-projection/v1")
        self.assertEqual(projection["layout"]["strategy"], "structured-lanes/v1")
        self.assertEqual(projection["layout"]["detached_nodes"], [])

        by_id = {node["id"]: node for node in projection["nodes"]}
        self.assertEqual(by_id["entry"]["icon"], "beginend")
        self.assertEqual(by_id["n0001"]["icon"], "action")
        self.assertEqual(by_id["n0002"]["icon"], "if")
        self.assertEqual(by_id["n0004"]["semantic_kind"], "loop")
        self.assertEqual(by_id["n0004"]["icon"], "if")
        self.assertEqual(by_id["n0008"]["icon"], "action")
        self.assertEqual(by_id["exit"]["text"], "end")

        self.assertEqual(by_id["n0002"]["text"], "Remaining < 0")
        self.assertEqual(by_id["n0004"]["text"], "Remaining > 0")
        self.assertEqual(
            by_id["n0003"]["trace"]["source_text"], "Result := -Remaining;"
        )

        expected_lanes = {
            "entry": 0,
            "n0001": 0,
            "n0002": 0,
            "n0003": 1,
            "n0004": 0,
            "n0005": 1,
            "n0006": 1,
            "n0007": 0,
            "n0008": 1,
            "n0009": 0,
            "exit": 0,
        }
        self.assertEqual(
            {node_id: node["layout"]["lane"] for node_id, node in by_id.items()},
            expected_lanes,
        )

        expected_roles = [
            "next",
            "next",
            "true",
            "false",
            "next",
            "loop_body",
            "loop_exit",
            "next",
            "back",
            "true",
            "false",
            "return",
            "next",
        ]
        self.assertEqual(
            [edge["role"] for edge in projection["edges"]],
            expected_roles,
        )
        self.assertTrue(
            next(edge for edge in projection["edges"] if edge["role"] == "back")[
                "back"
            ]
        )

    def test_projection_is_byte_for_byte_deterministic(self):
        observation = observation_fixture()
        first = json.dumps(
            PROJECT_DRAKON.project_observation(observation),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        second = json.dumps(
            PROJECT_DRAKON.project_observation(copy.deepcopy(observation)),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        self.assertEqual(first, second)

    def test_cli_requires_only_normalized_json_not_ada_or_frontend(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "observation.json"
            output_path = root / "projection.json"
            input_path.write_text(json.dumps(observation_fixture()), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            projection = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                projection["source"]["path"], observation_fixture()["source"]["path"]
            )
            self.assertNotIn("frontend", projection)

    def test_incomplete_observation_fails_closed(self):
        observation = observation_fixture()
        observation["complete"] = False
        with self.assertRaisesRegex(
            PROJECT_DRAKON.ProjectionError, "must be complete"
        ):
            PROJECT_DRAKON.project_observation(observation)

    def test_invalid_decision_contract_fails_closed(self):
        observation = observation_fixture()
        observation["edges"] = [
            edge
            for edge in observation["edges"]
            if not (
                edge["from"] == "n0002"
                and edge["to"] == "n0004"
                and edge["role"] == "false"
            )
        ]
        with self.assertRaisesRegex(
            PROJECT_DRAKON.ProjectionError, "decision must have exactly one true"
        ):
            PROJECT_DRAKON.project_observation(observation)

    def test_unreachable_source_node_remains_explicit(self):
        observation = observation_fixture()
        detached = source_node(
            "n0010", "action", "Result := 99;", "AssignStmt"
        )
        observation["nodes"].insert(-1, detached)
        observation["edges"].insert(
            -1, {"from": "n0010", "to": "exit", "role": "next"}
        )

        projection = PROJECT_DRAKON.project_observation(observation)
        by_id = {node["id"]: node for node in projection["nodes"]}

        self.assertFalse(by_id["n0010"]["layout"]["reachable"])
        self.assertEqual(by_id["n0010"]["layout"]["lane"], -1)
        self.assertEqual(projection["layout"]["detached_nodes"], ["n0010"])
        self.assertEqual(
            by_id["n0010"]["trace"]["source_text"],
            "Result := 99;",
        )


if __name__ == "__main__":
    unittest.main()
