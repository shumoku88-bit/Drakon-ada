#!/usr/bin/env python3
"""Run DRAKON Editor with the Repository Browser in an isolated disposable runtime.

This launcher ensures:
1. Pinned upstream checkout remains strictly clean and unmodified.
2. An isolated runtime is constructed under ``build/editor-runtime/``.
3. The Ada/SPARK code generator plugin is installed.
4. The Repository Browser extension is installed and its catalog is generated.
5. DRAKON Editor is launched with all command-line arguments preserved.
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


def setup_runtime(force_clean: bool = False) -> Path:
    """Prepare the disposable runtime under build/editor-runtime/."""
    verify_upstream_pinned()

    if force_clean and RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR)

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    # Synchronise upstream files into disposable runtime
    # We copy all files from UPSTREAM without touching .git
    for item in UPSTREAM.iterdir():
        if item.name == ".git":
            continue
        dest = RUNTIME_DIR / item.name
        if item.is_dir():
            if not dest.exists():
                shutil.copytree(item, dest)
            else:
                # Update files within directory
                for sub in item.rglob("*"):
                    rel = sub.relative_to(item)
                    target = dest / rel
                    if sub.is_file():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists() or sub.stat().st_mtime > target.stat().st_mtime:
                            shutil.copy2(sub, target)
        else:
            if not dest.exists() or item.stat().st_mtime > dest.stat().st_mtime:
                shutil.copy2(item, dest)

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

    # Img shim for environments where libtk-img is absent
    img_shim = """if {[catch {package require Img}]} {\n    package provide Img 1.0\n}\n"""
    if "package provide Img 1.0" not in tcl_content:
        tcl_content = img_shim + tcl_content

    # Repository Browser hook right after mw::create_ui
    hook = (
        'mw::create_ui\n'
        'source "$script_path/extensions/repository_browser.tcl"\n'
        'repobrowser::install_ui\n'
    )
    if "repobrowser::install_ui" not in tcl_content:
        tcl_content = tcl_content.replace("mw::create_ui\n", hook, 1)

    editor_tcl.write_text(tcl_content, encoding="utf-8")

    # 4. Generate repository catalog for browser tree
    catalog_file = RUNTIME_DIR / "repository_catalog.json"
    generator_script = ROOT / "tools" / "repository_browser.py"
    subprocess.run(
        [sys.executable, str(generator_script), "--root", str(ROOT), "--output", str(catalog_file)],
        check=True,
    )

    return RUNTIME_DIR / "drakon_editor.tcl"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run DRAKON Editor with Repository Browser in isolated runtime",
        add_help=False,
    )
    parser.add_argument("--clean", action="store_true", help="Rebuild editor-runtime from scratch")
    parser.add_argument("--help", "-h", action="store_true", help="Show help message")

    # Split known flags from editor arguments
    args, editor_args = parser.parse_known_args()

    if args.help:
        parser.print_help()
        print("\nAdditional arguments will be passed directly to DRAKON Editor (e.g. diagram.drn).")
        return

    editor_entry = setup_runtime(force_clean=args.clean)

    env = os.environ.copy()
    env["DRAKON_REPO_ROOT"] = str(ROOT)

    # Look for wish binary
    wish_cmd = shutil.which("wish") or "/usr/local/bin/wish"
    if not Path(wish_cmd).exists():
        raise SystemExit(f"wish binary not found at {wish_cmd}")

    cmd = [wish_cmd, str(editor_entry), *editor_args]
    print(f"Launching DRAKON Editor (runtime: {RUNTIME_DIR}) ...")
    try:
        res = subprocess.run(cmd, env=env)
        sys.exit(res.returncode)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
