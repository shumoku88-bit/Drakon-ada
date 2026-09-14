#!/usr/bin/env python3
"""Tests for DRAKON Editor Repository Browser and Runtime Launcher."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools import repository_browser as rb
from tools import run_editor

ROOT = Path(__file__).resolve().parents[1]


class RepositoryDiscoveryTests(unittest.TestCase):
    def test_discovery_canonical(self) -> None:
        canonical = rb.discover_canonical_files(ROOT)
        self.assertGreaterEqual(len(canonical), 5)
        rel_paths = {str(p.relative_to(ROOT)) for p in canonical}
        expected = {
            "examples/loam-balance-probe/loam_balance_probe.drn",
            "examples/loam-bounded-changes-probe/array_fold.drn",
            "examples/loam-active-prefix-probe/active_prefix_fold.drn",
            "examples/control-flow/branch/branch.drn",
            "examples/control-flow/countdown/countdown.drn",
            "examples/movement/movement.drn",
        }
        for exp in expected:
            self.assertIn(exp, rel_paths)

    def test_positive_working_build_resolves_noop_clean(self) -> None:
        """Verify that working resolution prefers human-approved noop-clean."""
        working = rb.discover_working_files(ROOT, canonical_diagram_names=set())
        rel_paths = {str(p.relative_to(ROOT)) for p in working}
        self.assertIn("build/quantity-at-two/noop-clean/quantity_at_two.drn", rel_paths)
        # Unapproved / intermediate copies must not be exposed
        self.assertNotIn("build/quantity-at-two/quantity_at_two.drn", rel_paths)
        self.assertNotIn("build/quantity-at-two/negative-pairing/quantity_at_two.drn", rel_paths)

    def test_canonical_promotion_overrides_working(self) -> None:
        """If a diagram name is discovered in canonical examples/, working candidate is skipped."""
        working = rb.discover_working_files(ROOT, canonical_diagram_names={"Quantity_At_Two"})
        rel_paths = {str(p.relative_to(ROOT)) for p in working}
        self.assertNotIn("build/quantity-at-two/noop-clean/quantity_at_two.drn", rel_paths)

    def test_diagram_names(self) -> None:
        probe = ROOT / "examples" / "loam-active-prefix-probe" / "active_prefix_fold.drn"
        diagrams = rb.inspect_drn_diagrams(probe)
        self.assertEqual(len(diagrams), 1)
        self.assertEqual(diagrams[0]["diagram_id"], 1)
        self.assertEqual(diagrams[0]["name"], "Fold_Active_Prefix")

    def test_catalog_hierarchy_and_node_resolution(self) -> None:
        catalog = rb.build_catalog_tree(ROOT, include_build=True)
        nodes = catalog["nodes"]
        self.assertGreater(len(nodes), 10)

        node_map = {n["id"]: n for n in nodes}
        root_node = node_map.get("root:repo")
        self.assertIsNotNone(root_node)
        self.assertEqual(root_node["text"], "Drakon-ada")

        # Verify all non-root nodes point to existing parents
        for n in nodes:
            parent_id = n.get("parent")
            if parent_id:
                self.assertIn(
                    parent_id,
                    node_map,
                    f"Orphan node {n['id']} points to non-existent parent {parent_id}",
                )

        # Verify diagram nodes have valid file paths and IDs
        diagram_nodes = [n for n in nodes if n["type"] == "diagram"]
        self.assertGreaterEqual(len(diagram_nodes), 6)
        for dia in diagram_nodes:
            self.assertIn("diagram_id", dia)
            self.assertIn("abs_path", dia)
            self.assertTrue(Path(dia["abs_path"]).exists(), f"File does not exist: {dia['abs_path']}")


class SwitchingPurityTests(unittest.TestCase):
    def test_file_switching_does_not_mutate_bytes(self) -> None:
        """Verify that opening and switching files in Tcl does not modify file contents."""
        files = [
            ROOT / "examples/control-flow/branch/branch.drn",
            ROOT / "examples/loam-bounded-changes-probe/array_fold.drn",
            ROOT / "examples/loam-active-prefix-probe/active_prefix_fold.drn",
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            copies: list[Path] = []
            hashes_before: list[str] = []
            for f in files:
                dst = Path(tmpdir) / f.name
                shutil.copy2(f, dst)
                copies.append(dst)
                hashes_before.append(hashlib.sha256(dst.read_bytes()).hexdigest())

            script = f"""
            if {{[catch {{package require Img}}]}} {{
                package provide Img 1.0
            }}
            set argv [list "{copies[0]}"]
            set argc 1

            proc test_switch {{filename}} {{
                set filename [file normalize $filename]
                hl::reset
                if {{[info exists mod::db_names($ds::db)]}} {{
                    mod::close $ds::db
                }}
                ds::openfile $filename
            }}

            after 150 {{
                test_switch "{copies[0]}"
                test_switch "{copies[1]}"
                test_switch "{copies[2]}"
                test_switch "{copies[0]}"
                test_switch "{copies[1]}"
                exit 0
            }}

            cd "{ROOT / 'build/editor-runtime'}"
            source drakon_editor.tcl
            """

            with tempfile.NamedTemporaryFile("w", suffix=".tcl", delete=False) as tf:
                tf.write(script)
                tmp_script = tf.name

            wish = shutil.which("wish") or "/usr/local/bin/wish"
            res = subprocess.run([wish, tmp_script], capture_output=True, text=True, timeout=10)
            self.assertEqual(res.returncode, 0, f"Wish failed:\n{res.stderr}")

            for dst, h_before in zip(copies, hashes_before):
                h_after = hashlib.sha256(dst.read_bytes()).hexdigest()
                self.assertEqual(
                    h_before,
                    h_after,
                    f"File bytes mutated after switching for {dst.name}",
                )


class UpstreamCleanTests(unittest.TestCase):
    def test_pinned_upstream_remains_clean(self) -> None:
        """Upstream checkout must have zero tracked modifications."""
        upstream = ROOT / ".upstream/drakon_editor"
        dirty = subprocess.check_output(
            ["git", "-C", str(upstream), "status", "--porcelain", "--untracked-files=no"],
            text=True,
        ).strip()
        self.assertEqual(dirty, "", f"Upstream tracked files are dirty:\n{dirty}")


class RuntimeSetupTests(unittest.TestCase):
    def test_setup_runtime_construction(self) -> None:
        entry = run_editor.setup_runtime()
        self.assertTrue(entry.exists())

        runtime_dir = ROOT / "build/editor-runtime"
        self.assertTrue((runtime_dir / "generators/ada.tcl").exists())
        self.assertTrue((runtime_dir / "extensions/repository_browser.tcl").exists())
        self.assertTrue((runtime_dir / "repository_catalog.json").exists())

        # Verify minimal patch in runtime copy
        content = entry.read_text(encoding="utf-8")
        self.assertIn("repobrowser::install_ui", content)
        self.assertIn("package provide Img 1.0", content)

    def test_end_to_end_repository_browser(self) -> None:
        """Headless verification of notebook, tree population, and node activation."""
        run_editor.setup_runtime()

        test_script = f"""
        after 150 {{
            if {{![winfo exists .root.pnd.nb]}} {{
                puts "FAIL: notebook not found"
                exit 1
            }}
            set tree .root.pnd.repo.tf.tree
            if {{![winfo exists $tree]}} {{
                puts "FAIL: tree not found"
                exit 1
            }}
            set nodes [$tree children root:repo]
            if {{[llength $nodes] == 0}} {{
                puts "FAIL: no group nodes found under root"
                exit 1
            }}

            # Find active prefix diagram node
            set target_node ""
            foreach n [array names repobrowser::node_target] {{
                lassign $repobrowser::node_target($n) path dia_id ntype
                if {{[string match "*active_prefix_fold.drn" $path] && $ntype eq "diagram"}} {{
                    set target_node $n
                    break
                }}
            }}
            if {{$target_node eq ""}} {{
                puts "FAIL: active_prefix_fold diagram node not found"
                exit 1
            }}

            # Activate diagram
            $tree selection set $target_node
            repobrowser::on_select
            update

            set cur_title [wm title .]
            if {{![string match "*active_prefix_fold.drn*" $cur_title]}} {{
                puts "FAIL: expected active_prefix_fold in window title, got: $cur_title"
                exit 1
            }}

            puts "PASSED"
            exit 0
        }}

        set argv [list "{ROOT / 'examples/control-flow/branch/branch.drn'}"]
        set argc 1

        cd "{ROOT / 'build/editor-runtime'}"
        source drakon_editor.tcl
        """

        with tempfile.NamedTemporaryFile("w", suffix=".tcl", delete=False) as tf:
            tf.write(test_script)
            tmp_script = tf.name

        wish = shutil.which("wish") or "/usr/local/bin/wish"
        res = subprocess.run([wish, tmp_script], capture_output=True, text=True, timeout=10)
        self.assertEqual(res.returncode, 0, f"Wish failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        self.assertIn("PASSED", res.stdout)


if __name__ == "__main__":
    unittest.main()
