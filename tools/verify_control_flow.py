#!/usr/bin/env python3
"""Qualify minimal if/loop generation and explicit loop contracts."""
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
WORK = ROOT / 'build/control-flow'


def run(args, log, success=True):
    result = subprocess.run(list(map(str, args)), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=120)
    print(result.stdout, end='')
    log.write_text(result.stdout)
    if success and result.returncode:
        raise SystemExit(f'Failed ({result.returncode}): {args}')
    return result


if WORK.exists():
    shutil.rmtree(WORK)
EVIDENCE = WORK / 'evidence'
EVIDENCE.mkdir(parents=True)
run([sys.executable, 'tools/setup.py'], EVIDENCE / 'setup.txt')
runner = [os.environ.get('TCLSH', 'tclsh'), 'integration/drakon-editor/generate.tcl']
for name in ('branch', 'countdown'):
    run([*runner, f'examples/control-flow/{name}/{name}.drn', WORK / 'generated'],
        EVIDENCE / f'generate-{name}.txt')
project = 'examples/control-flow/control_flow.gpr'
run(['gprbuild', '-p', '-P', project], EVIDENCE / 'compile.txt')
flags = ['--mode=all', '--report=all', '--checks-as-errors=on', '--warnings=error', '--level=2']
result = run(['gnatprove', '-P', project, '-u', 'branch.adb', 'countdown.adb', *flags],
             EVIDENCE / 'prove.txt')
summary = (WORK / 'obj/gnatprove/gnatprove.out').read_text()
(EVIDENCE / 'gnatprove.out').write_text(summary)
if ('Success: all checks proved (11 checks)' not in result.stdout
        or not re.search(r'^Total\s+11\s+3 \(27%\)\s+8 \(73%\)\s+\.\s+\.\s*$', summary, re.M)
        or summary.count('0 pragma Assume statements') != 4
        or 'Analyzed 2 units' not in summary):
    raise SystemExit('Unexpected coverage, proof counts, assumptions or report format')
run([WORK / 'bin/control_flow_test'], EVIDENCE / 'runtime.txt')

# Only mutate authoritative source diagrams/properties, never generated Ada.
mutations = [
    ('wrong-branch', 'branch', "UPDATE items SET text='Result := 0;' WHERE item_id=10", 'postcondition might fail'),
    ('no-progress', 'countdown', "UPDATE items SET text='Count := Count;' WHERE item_id=9", 'loop variant might fail'),
    ('weak-invariant', 'countdown', "UPDATE diagram_info SET value=replace(value,'invariant {Count > 0 and then Count <= Amount}','invariant {Count <= Amount}')", 'range check might fail'),
]
for label, name, sql, expected in mutations:
    work = WORK / label
    work.mkdir()
    source = work / f'{name}.drn'
    shutil.copyfile(f'examples/control-flow/{name}/{name}.drn', source)
    with sqlite3.connect(source) as db:
        db.execute(sql)
    run([*runner, source, work / 'generated'], EVIDENCE / f'{label}-generate.txt')
    gpr = work / 'negative.gpr'
    gpr.write_text('''project Negative is
   for Languages use ("Ada");
   for Source_Dirs use ("generated");
   for Object_Dir use "obj";
   package Compiler is
      for Default_Switches ("Ada") use ("-gnat2022", "-gnata", "-gnato");
   end Compiler;
end Negative;
''')
    run(['gprbuild', '-p', '-c', '-P', gpr], EVIDENCE / f'{label}-compile.txt')
    result = run(['gnatprove', '-P', gpr, '-u', name + '.adb', *flags],
                 EVIDENCE / f'{label}-prove.txt', success=False)
    if result.returncode == 0 or expected not in result.stdout:
        raise SystemExit(f'{label}: expected nonzero proof result with {expected!r}')
print('PASS: structured if/loop, all 11 checks, all 32 inputs, three negative proof controls')
