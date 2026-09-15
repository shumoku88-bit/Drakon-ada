"""Phase O4 end-to-end observation command qualification."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

SPEC = importlib.util.spec_from_file_location(
    "observe_to_drakon", TOOLS / "observe_to_drakon.py"
)
assert SPEC is not None and SPEC.loader is not None
PIPELINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PIPELINE)


class ObserveToDrakonTests(unittest.TestCase):
    def test_pipeline_composes_existing_stages_in_order(self):
        calls = []
        observation = {"source": {"path": "examples/demo.adb"}}
        projection = {"schema": "projection"}

        def observer(source, source_root, charset):
            calls.append(("observe", source, source_root, charset))
            return observation

        def projector(value):
            calls.append(("project", value))
            return projection

        def writer(value, path):
            calls.append(("write", value, path))
            path.write_bytes(b"derived-drn")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "demo.adb"
            output = root / "out.drn"

            result = PIPELINE.observe_to_drakon(
                source,
                source_root=root,
                output=output,
                charset="latin-1",
                observer=observer,
                projector=projector,
                writer=writer,
            )

            self.assertEqual(result, output)
            self.assertEqual(output.read_bytes(), b"derived-drn")
            self.assertEqual(calls[0], ("observe", source, root, "latin-1"))
            self.assertEqual(calls[1], ("project", observation))
            self.assertEqual(calls[2][0:2], ("write", projection))
            self.assertNotEqual(calls[2][2], output)
            self.assertFalse(any(root.glob("*.json")))

    def test_default_output_follows_observation_source_identity(self):
        def observer(source, source_root, charset):
            return {"source": {"path": "examples/source-observation/demo.adb"}}

        def writer(projection, path):
            path.write_bytes(b"ok")

        with tempfile.TemporaryDirectory() as directory:
            build_root = Path(directory) / "build" / "drakon"
            with mock.patch.object(PIPELINE, "BUILD_ROOT", build_root):
                result = PIPELINE.observe_to_drakon(
                    Path("demo.adb"),
                    observer=observer,
                    projector=lambda observation: {"projection": observation},
                    writer=writer,
                )

            expected = (
                build_root / "examples" / "source-observation" / "demo.drn"
            )
            self.assertEqual(result, expected)
            self.assertEqual(expected.read_bytes(), b"ok")

    def test_writer_failure_preserves_existing_output_and_cleans_temporary(self):
        def writer(projection, path):
            path.write_bytes(b"partial")
            raise PIPELINE.write_drakon.WriterError("synthetic failure")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "existing.drn"
            output.write_bytes(b"previous")

            with self.assertRaisesRegex(
                PIPELINE.write_drakon.WriterError, "synthetic failure"
            ):
                PIPELINE.observe_to_drakon(
                    root / "demo.adb",
                    output=output,
                    observer=lambda source, source_root, charset: {
                        "source": {"path": "demo.adb"}
                    },
                    projector=lambda observation: {"projection": observation},
                    writer=writer,
                )

            self.assertEqual(output.read_bytes(), b"previous")
            self.assertEqual(list(root.glob(".existing.drn.*.tmp")), [])

    def test_unsafe_default_source_identity_fails_closed(self):
        with self.assertRaisesRegex(
            PIPELINE.PipelineError, "unsafe observation source path"
        ):
            PIPELINE.observe_to_drakon(
                Path("demo.adb"),
                observer=lambda source, source_root, charset: {
                    "source": {"path": "../demo.adb"}
                },
                projector=lambda observation: {"projection": observation},
                writer=lambda projection, path: self.fail("writer must not run"),
            )

    def test_main_forwards_cli_arguments_without_reimplementing_pipeline(self):
        expected = Path("build/custom.drn")
        captured = {}

        def fake_pipeline(source, *, source_root, output, charset):
            captured.update(
                source=source,
                source_root=source_root,
                output=output,
                charset=charset,
            )
            return expected

        stdout = io.StringIO()
        with mock.patch.object(PIPELINE, "observe_to_drakon", fake_pipeline):
            with redirect_stdout(stdout):
                status = PIPELINE.main(
                    [
                        "examples/demo.adb",
                        "--source-root",
                        "examples",
                        "--output",
                        str(expected),
                        "--charset",
                        "latin-1",
                    ]
                )

        self.assertEqual(status, 0)
        self.assertEqual(captured["source"], Path("examples/demo.adb"))
        self.assertEqual(captured["source_root"], Path("examples"))
        self.assertEqual(captured["output"], expected)
        self.assertEqual(captured["charset"], "latin-1")
        self.assertEqual(stdout.getvalue().strip(), str(expected))


if __name__ == "__main__":
    unittest.main()
