#!/usr/bin/env python3
"""Verify a temporary clean Git clone without committing the working repo."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=None):
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


# Include current tracked/untracked project sources, honoring .gitignore.
files = subprocess.check_output(
    ['git', '-C', str(ROOT), 'ls-files', '-co', '--exclude-standard', '-z'])
with tempfile.TemporaryDirectory(prefix='drakon-ada-clean-') as tmp:
    seed = Path(tmp) / 'seed'
    clone = Path(tmp) / 'checkout'
    seed.mkdir()
    for name in set(files.decode().split('\0')) - {''}:
        source = ROOT / name
        if not source.is_file():
            raise SystemExit(f'Expected source file: {name}')
        target = seed / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    run('git', 'init', '-q', seed)
    run('git', 'add', '.', cwd=seed)
    # Test-only identity and commit in a disposable seed repository.
    run('git', '-c', 'user.name=Reproduction Test',
        '-c', 'user.email=reproduction@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Test source snapshot', cwd=seed)
    run('git', 'clone', '-q', '--no-local', seed, clone)
    run(sys.executable, 'tools/verify.py', cwd=clone)
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=clone)
    if dirty:
        raise SystemExit(f'Clean checkout was modified: {dirty.decode()}')
    evidence = ROOT / 'build/evidence/clean-checkout.txt'
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text('PASS: temporary clean Git clone; dependencies fetched anew; '
                        'full verify gate passed; git status clean.\n'
                        'Existing PATH toolchain reused; not a clean OS image.\n')
print('PASS: clean Git checkout; original repository has not been committed')
