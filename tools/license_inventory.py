#!/usr/bin/env python3
"""Emit a per-source-file notice inventory from the pinned Git objects.

This is a keyword inventory, not a license classifier or a legal determination.
No working-tree plugin or binary/document contents are included.
"""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / '.upstream/drakon_editor'
LOCK = dict(line.split() for line in (ROOT / 'upstream.lock').read_text().splitlines())
COMMIT = LOCK['commit']
EXTENSIONS = set('tcl c h cpp cs ahk erl sh js java py lua pde sql m pch '
                 'kum d go bat cmd v nools msg'.split())
PATTERN = re.compile(r'copyright|public domain|licen[sc]e|redistribut', re.I)


def git(*args):
    return subprocess.check_output(['git', '-C', str(UPSTREAM), *args])


print('path\tnotice_keyword_lines_in_entire_source')
for path in git('ls-tree', '-r', '--name-only', COMMIT).decode().splitlines():
    if Path(path).suffix.lstrip('.') not in EXTENSIONS:
        continue
    text = git('show', f'{COMMIT}:{path}').decode('utf-8', errors='replace')
    matches = [f'{i}: {line.strip()}' for i, line in enumerate(text.splitlines(), 1)
               if PATTERN.search(line)]
    value = ' | '.join(matches) if matches else 'NONE (no keyword match; not a license grant)'
    print(path + '\t' + value.replace('\t', ' '))
