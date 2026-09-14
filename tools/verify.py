#!/usr/bin/env python3
"""Full gate: fresh generation, compile, proof, runtime, and a negative proof."""
from pathlib import Path
import os
import re
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
BUILD = ROOT / 'build'


def run(args, log=None, success=True):
    result = subprocess.run(list(map(str, args)), text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    print(result.stdout, end='')
    if log:
        Path(log).write_text(result.stdout)
    if success and result.returncode != 0:
        raise SystemExit(f'FAILED ({result.returncode}): {args}')
    return result


for tool in (os.environ.get('TCLSH', 'tclsh'), 'gprbuild', 'gnatprove'):
    if not shutil.which(tool):
        raise SystemExit(f'Missing {tool}; see docs/reproduction.md (not a skipped success)')
# Never let stale generated files or proof sessions satisfy the gate.
if BUILD.exists():
    shutil.rmtree(BUILD)
(BUILD / 'evidence').mkdir(parents=True)
run([sys.executable, 'tools/setup.py'])
for tool in ('gprbuild', 'gnatprove'):
    run([tool, '--version'], BUILD / f'evidence/{tool}-version.txt')
run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
    BUILD / 'evidence/generation-tests.txt')
runner = [os.environ.get('TCLSH', 'tclsh'), 'integration/drakon-editor/generate.tcl']
run([*runner, 'examples/movement/movement.drn', 'build/generated'])
project = 'examples/movement/movement.gpr'
run(['gprbuild', '-p', '-P', project], BUILD / 'evidence/compile.txt')
proof_flags = ['-u', 'movement.adb', '--mode=all', '--report=all',
               '--checks-as-errors=on', '--warnings=error', '--level=2']
result = run(['gnatprove', '-P', project, *proof_flags], BUILD / 'evidence/prove.txt')
summary = (BUILD / 'obj/gnatprove/gnatprove.out').read_text()
(BUILD / 'evidence/gnatprove.out').write_text(summary)
# This is a deliberately version-sensitive movement gate. Review changes,
# rather than accepting a new report format or a vacuous proof silently.
if not re.search(r'Success: all checks proved \(3 checks\)', result.stdout):
    raise SystemExit('Expected 2 initialization checks and 1 functional check')
if '0 pragma Assume statements' not in summary:
    raise SystemExit('Missing assumption audit in report')
if not re.search(r'^Total\s+3\s+2 \(67%\)\s+1 \(33%\)\s+\.\s+\.\s*$', summary, re.M):
    raise SystemExit('Unexpected proof totals / justified / unproved checks')
run(['build/bin/movement_test'], BUILD / 'evidence/runtime.txt')

# Mutation must start from the DRAKON source, not edited generated Ada.
negative = BUILD / 'negative'
negative.mkdir()
source = negative / 'movement.drn'
shutil.copyfile('examples/movement/movement.drn', source)
with sqlite3.connect(source) as db:
    db.execute("UPDATE items SET text = 'Source := Amount;' WHERE item_id = 4")
run([*runner, source, negative / 'generated'])
(negative / 'negative.gpr').write_text('''project Negative is
   for Languages use ("Ada");
   for Source_Dirs use ("generated");
   for Object_Dir use "obj";
   package Compiler is
      for Default_Switches ("Ada") use ("-gnat2022", "-gnata", "-gnato");
   end Compiler;
end Negative;
''')
# Establish that proof failure is not just a syntax or build failure.
run(['gprbuild', '-p', '-c', '-P', negative / 'negative.gpr'])
result = run(['gnatprove', '-P', negative / 'negative.gpr', *proof_flags],
             BUILD / 'evidence/negative-proof.txt', success=False)
if result.returncode == 0 or 'postcondition might fail' not in result.stdout:
    raise SystemExit('Negative proof control did not fail for the expected reason')
print('PASS: generation, compile, non-vacuous proof, runtime, negative proof control')
