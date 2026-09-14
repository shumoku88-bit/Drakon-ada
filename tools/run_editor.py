#!/usr/bin/env python3
"""Run DRAKON Editor with the Repository Browser in an isolated disposable runtime.

Guarantees:
1. Pinned upstream checkout (.upstream/drakon_editor) remains strictly clean.
2. The runtime directory (build/editor-runtime/) is deterministically recreated
   from scratch on every launch, leaving zero stale files.
3. The Ada/SPARK code generator and Repository Browser extension are installed.
4. Minimal 2-line hook is injected into the runtime copy of drakon_editor.tcl.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = ROOT / "upstream.lock"
UPSTREAM = ROOT / ".upstream" / "drakon_editor"
RUNTIME_DIR = ROOT / "build" / "editor-runtime"


def git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *map(str, args)], cwd=cwd, text=True).strip()


def verify_upstream_pinned() -> None:
    """Ensure upstream matches exact commit and has no tracked modifications."""
    if not LOCK_FILE.exists():
        raise SystemExit("Missing upstream.lock")

    lock = dict(line.split() for line in LOCK_FILE.read_text().splitlines())
    expected_commit = lock.get("commit")

    if not UPSTREAM.exists():
        raise SystemExit(f"Upstream checkout not found at {UPSTREAM}. Run tools/setup.py first.")

    current_commit = git(UPSTREAM, "rev-parse", "HEAD")
    if current_commit != expected_commit:
        raise SystemExit(
            f"Upstream commit mismatch: expected {expected_commit}, got {current_commit}"
        )

    dirty = git(UPSTREAM, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise SystemExit(
            f"Upstream tracked files are modified; refusing to proceed:\n{dirty}"
        )


def setup_runtime() -> Path:
    """Deterministically construct the disposable runtime under build/editor-runtime/."""
    verify_upstream_pinned()

    # Always recreate from scratch to guarantee zero stale files
    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR)

    shutil.copytree(UPSTREAM, RUNTIME_DIR, ignore=shutil.ignore_patterns(".git"))

    # 1. Install Ada/SPARK code generator plugin
    ada_src = ROOT / "generator" / "ada.tcl"
    ada_dest = RUNTIME_DIR / "generators" / "ada.tcl"
    ada_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ada_src, ada_dest)

    # 2. Install Repository Browser extension outside scripts/ to avoid glob collisions
    ext_dir = RUNTIME_DIR / "extensions"
    ext_dir.mkdir(parents=True, exist_ok=True)
    browser_src = ROOT / "integration" / "drakon-editor" / "repository_browser.tcl"
    browser_dest = ext_dir / "repository_browser.tcl"
    shutil.copy2(browser_src, browser_dest)

    # 3. Apply minimal hook (2 lines) and Img shim to runtime copy of drakon_editor.tcl
    editor_tcl = RUNTIME_DIR / "drakon_editor.tcl"
    tcl_content = editor_tcl.read_text(encoding="utf-8")

    img_shim = "if {[catch {package require Img}]} {\n    package provide Img 1.0\n}\n"
    hook = (
        'mw::create_ui\n'
        'source "$script_path/extensions/repository_browser.tcl"\n'
        'repobrowser::install_ui\n'
    )
    tcl_content = img_shim + tcl_content.replace("mw::create_ui\n", hook, 1)
    editor_tcl.write_text(tcl_content, encoding="utf-8")

    # 4. Generate repository catalog for browser tree
    catalog_file = RUNTIME_DIR / "repository_catalog.json"
    generator_script = ROOT / "tools" / "repository_browser.py"
    subprocess.run(
        [sys.executable, str(generator_script), "--root", str(ROOT), "--output", str(catalog_file)],
        check=True,
    )

    return editor_tcl


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run DRAKON Editor with Repository Browser in disposable runtime",
        add_help=False,
    )
    parser.add_argument("--clean", action="store_true", help="Explicitly rebuild runtime (already default)")
    parser.add_argument("--help", "-h", action="store_true", help="Show help message")

    args, editor_args = parser.parse_known_args()

    if args.help:
        parser.print_help()
        print("\nAdditional arguments are passed to DRAKON Editor (e.g. file.drn).")
        return

    editor_entry = setup_runtime()

    env = os.environ.copy()
    env["DRAKON_REPO_ROOT"] = str(ROOT)

    wish_cmd = shutil.which("wish") or "/usr/local/bin/wish"
    if not Path(wish_cmd).exists():
        raise SystemExit(f"wish binary not found at {wish_cmd}")

    cmd = [wish_cmd, str(editor_entry), *editor_args]
    print(f"Launching DRAKON Editor (disposable runtime: {RUNTIME_DIR}) ...")
    try:
        res = subprocess.run(cmd, env=env)
        sys.exit(res.returncode)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
