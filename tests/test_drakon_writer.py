"""Phase O3b DRAKON Editor SQLite writer qualification."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/write_drakon.py"
FIXTURE = ROOT / "examples/drakon-projection/observation_fixture_projection.json"

SPEC = importlib.util.spec_from_file_location("write_drakon", TOOL)
assert SPEC is not None and SPEC.loader is not None
WRITE_DRAKON = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WRITE_DRAKON)


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_map(path: Path):
    with sqlite3.connect(path) as db:
        value = db.execute(
            "SELECT value FROM diagram_info WHERE name=?",
            (WRITE_DRAKON.MAP_SCHEMA,),
        ).fetchone()[0]
    return json.loads(value)


def canonical_rows(path: Path):
    with sqlite3.connect(path) as db:
        return {
            "info": db.execute(
                "SELECT key, value FROM info ORDER BY key"
            ).fetchall(),
            "diagrams": db.execute(
                "SELECT diagram_id, name, origin, description, zoom "
                "FROM diagrams ORDER BY diagram_id"
            ).fetchall(),
            "state": db.execute(
                "SELECT row, current_dia, description FROM state ORDER BY row"
            ).fetchall(),
            "tree_nodes": db.execute(
                "SELECT node_id, parent, type, name, diagram_id "
                "FROM tree_nodes ORDER BY node_id"
            ).fetchall(),
            "items": db.execute(
                "SELECT item_id, diagram_id, type, text, selected, "
                "x, y, w, h, a, b, aux_value, color, format, text2 "
                "FROM items ORDER BY item_id"
            ).fetchall(),
            "diagram_info": db.execute(
                "SELECT diagram_id, name, value "
                "FROM diagram_info ORDER BY diagram_id, name"
            ).fetchall(),
        }


class DrakonWriterTests(unittest.TestCase):
    def write(self, projection=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        output = Path(directory.name) / "fixture.drn"
        WRITE_DRAKON.write_projection(projection or fixture(), output)
        return output

    def test_fixture_writes_editor_schema_and_signature(self):
        output = self.write()
        self.assertTrue(output.read_bytes().startswith(b"SQLite format 3\x00"))
        with sqlite3.connect(output) as db:
            self.assertEqual(
                dict(db.execute("SELECT key, value FROM info")),
                {
                    "type": "drakon",
                    "version": "2",
                    "start_version": "1",
                    "language": "SPARK",
                },
            )
            self.assertEqual(
                db.execute(
                    "SELECT name, origin, zoom FROM diagrams WHERE diagram_id=1"
                ).fetchone(),
                ("Observation_Fixture", "0 0", 100.0),
            )
            self.assertEqual(
                db.execute(
                    "SELECT parent, type, diagram_id "
                    "FROM tree_nodes WHERE node_id=1"
                ).fetchone(),
                (0, "item", 1),
            )

    def test_fixture_uses_loop_aware_physical_lanes_and_return_arrow(self):
        output = self.write()
        mapping = load_map(output)
        by_id = {node["node_id"]: node for node in mapping["nodes"]}

        # The loop completion is pushed below the complete loop body.
        self.assertEqual(by_id["n0007"]["physical"]["rank"], 6)
        self.assertEqual(by_id["exit"]["physical"]["rank"], 8)

        # The inner loop gets lane 1, the enclosing bypass lane 2, and the
        # later branch can reuse lane 1 after the loop has merged.
        self.assertEqual(by_id["n0003"]["physical"]["lane"], 2)
        self.assertEqual(by_id["n0005"]["physical"]["lane"], 1)
        self.assertEqual(by_id["n0006"]["physical"]["lane"], 1)
        self.assertEqual(by_id["n0008"]["physical"]["lane"], 1)
        self.assertEqual(by_id["n0003"]["physical"]["x"], 760)
        self.assertEqual(by_id["n0005"]["physical"]["x"], 500)

        with sqlite3.connect(output) as db:
            arrows = db.execute(
                "SELECT x, y, w, h, a, b FROM items WHERE type='arrow'"
            ).fetchall()
            self.assertEqual(arrows, [(630, 400, 390, 360, 130, 0)])

            # YES/body branches are intrinsic to the DRAKON if icon. The
            # outer decision reaches lane 2 and the loop reaches lane 1.
            if_rows = db.execute(
                "SELECT text, x, y, w, h, a, b "
                "FROM items WHERE type='if' ORDER BY item_id"
            ).fetchall()
            self.assertEqual(if_rows[0][-2:], (460, 0))
            self.assertEqual(if_rows[1][-2:], (200, 0))
            self.assertEqual(if_rows[2][-2:], (200, 0))

    def test_source_trace_and_semantic_edges_survive_in_diagram_metadata(self):
        projection = fixture()
        output = self.write(projection)
        mapping = load_map(output)

        self.assertEqual(mapping["schema"], "drakon-ada/drn-projection-map/v1")
        self.assertEqual(mapping["projection_schema"], projection["schema"])
        self.assertEqual(mapping["source"], projection["source"])
        self.assertEqual(mapping["edges"], projection["edges"])

        by_id = {node["node_id"]: node for node in mapping["nodes"]}
        original = {node["id"]: node for node in projection["nodes"]}
        self.assertEqual(
            by_id["n0003"]["trace"],
            original["n0003"]["trace"],
        )
        self.assertIsInstance(by_id["n0003"]["item_id"], int)

    def test_sqlite_content_is_deterministic(self):
        first = self.write()
        second = self.write(copy.deepcopy(fixture()))
        self.assertEqual(canonical_rows(first), canonical_rows(second))

    def test_detached_projection_fails_closed(self):
        projection = fixture()
        projection["layout"]["detached_nodes"] = ["n0099"]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                WRITE_DRAKON.WriterError, "cannot write detached nodes"
            ):
                WRITE_DRAKON.write_projection(
                    projection, Path(directory) / "bad.drn"
                )

    def test_structurally_valid_nested_branch_fails_closed(self):
        projection = fixture()
        by_id = {node["id"]: node for node in projection["nodes"]}
        nested = by_id["n0003"]
        nested["semantic_kind"] = "decision"
        nested["icon"] = "if"
        nested["text"] = "Nested = 1"

        # Make the nested node a valid decision first, so the failure proves
        # the O3b physical-layout boundary rather than a malformed role set.
        projection["edges"] = [
            edge
            for edge in projection["edges"]
            if not (edge["from"] == "n0003" and edge["role"] == "next")
        ]
        template = copy.deepcopy(by_id["n0001"])
        left = copy.deepcopy(template)
        left.update({"id": "n0010", "order": 10, "text": "Left := 1;"})
        left["layout"].update({"rank": 4, "lane": 2, "x": 760, "y": 580})
        right = copy.deepcopy(template)
        right.update({"id": "n0011", "order": 11, "text": "Right := 1;"})
        right["layout"].update({"rank": 4, "lane": 3, "x": 1020, "y": 580})
        by_id["exit"]["order"] = 12
        projection["nodes"].extend([left, right])
        projection["edges"].extend(
            [
                {"from": "n0003", "to": "n0010", "role": "true", "back": False},
                {"from": "n0003", "to": "n0011", "role": "false", "back": False},
                {"from": "n0010", "to": "n0007", "role": "next", "back": False},
                {"from": "n0011", "to": "n0007", "role": "next", "back": False},
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                WRITE_DRAKON.WriterError, "nested branch source"
            ):
                WRITE_DRAKON.write_projection(
                    projection, Path(directory) / "bad.drn"
                )

    def test_cli_consumes_projection_without_ada_or_libadalang(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fixture.drn"
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    str(FIXTURE),
                    str(output),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(output.exists())
            self.assertEqual(load_map(output)["source"], fixture()["source"])


if __name__ == "__main__":
    unittest.main()
