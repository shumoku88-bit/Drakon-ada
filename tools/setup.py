#!/usr/bin/env python3
"""Fetch the exact upstream and install only our plugin; no tracked file patch."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
lock = dict(line.split() for line in (ROOT / 'upstream.lock').read_text().splitlines())
upstream = ROOT / '.upstream/drakon_editor'


def git(*args):
    return subprocess.check_output(['git', *map(str, args)], text=True).strip()


if not upstream.exists():
    upstream.parent.mkdir(parents=True, exist_ok=True)
    git('clone', '--no-checkout', lock['repository'], upstream)
    git('-C', upstream, 'checkout', '--detach', lock['commit'])
if git('-C', upstream, 'rev-parse', 'HEAD') != lock['commit']:
    raise SystemExit('Upstream commit mismatch; refusing to change an existing checkout')
if git('-C', upstream, 'status', '--porcelain', '--untracked-files=no'):
    raise SystemExit('Upstream tracked files are modified; refusing installation')
shutil.copyfile(ROOT / 'generator/ada.tcl', upstream / 'generators/ada.tcl')
print(f'Installed Ada/SPARK plugin at {lock["commit"]}')
