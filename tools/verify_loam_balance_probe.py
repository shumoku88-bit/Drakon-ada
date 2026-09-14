#!/usr/bin/env python3
"""Focused gate for the canonical bounded LOAM balance-admission dogfood probe."""
from pathlib import Path
import os
import re
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
WORK = ROOT / "build/loam-balance-probe"
EVIDENCE = WORK / "evidence"
CANONICAL_SOURCE = ROOT / "examples/loam-balance-probe/loam_balance_probe.drn"
SOURCE = WORK / "loam_balance_probe.drn"


def run(args, log, success=True, timeout=120):
    result = subprocess.run(
        list(map(str, args)),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    print(result.stdout, end="")
    Path(log).write_text(result.stdout)
    if success and result.returncode != 0:
        raise SystemExit(f"FAILED ({result.returncode}): {args}")
    return result


def negative_control(label, sql, expected_diagnostics, proof_flags):
    work = WORK / label
    work.mkdir()
    source = work / "probe.drn"
    shutil.copyfile(SOURCE, source)
    with sqlite3.connect(source) as db:
        db.execute(sql)
    generated = work / "generated"
    runner = [
        os.environ.get("TCLSH", "tclsh"),
        "integration/drakon-editor/generate.tcl",
    ]
    run([*runner, source, generated], EVIDENCE / f"{label}-generate.txt")
    gpr = work / "negative.gpr"
    gpr.write_text(
        '''project Negative is
   for Languages use ("Ada");
   for Source_Dirs use ("generated");
   for Object_Dir use "obj";
   package Compiler is
      for Default_Switches ("Ada") use ("-gnat2022", "-gnata", "-gnato", "-gnatwe");
   end Compiler;
end Negative;
'''
    )
    run(["gprbuild", "-p", "-c", "-P", gpr], EVIDENCE / f"{label}-compile.txt")
    result = run(
        ["gnatprove", "-P", gpr, "-u", "loam_balance_admission.adb", *proof_flags],
        EVIDENCE / f"{label}-prove.txt",
        success=False,
    )
    if result.returncode == 0 or not any(
        diagnostic in result.stdout for diagnostic in expected_diagnostics
    ):
        raise SystemExit(
            f"{label}: expected proof failure containing one of {expected_diagnostics!r}"
        )


if WORK.exists():
    shutil.rmtree(WORK)
EVIDENCE.mkdir(parents=True)

for tool in (os.environ.get("TCLSH", "tclsh"), "gprbuild", "gnatprove"):
    if not shutil.which(tool):
        raise SystemExit(f"Missing {tool}; this probe is not a skipped success")

run([sys.executable, "tools/setup.py"], EVIDENCE / "setup.txt")
run(
    [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_loam_balance_probe.py",
        "-v",
    ],
    EVIDENCE / "generation-tests.txt",
)
shutil.copyfile(CANONICAL_SOURCE, SOURCE)
runner = [
    os.environ.get("TCLSH", "tclsh"),
    "integration/drakon-editor/generate.tcl",
]
run([*runner, SOURCE, WORK / "generated"], EVIDENCE / "generate.txt")

project = "examples/loam-balance-probe/loam_balance_probe.gpr"
run(["gprbuild", "-p", "-P", project], EVIDENCE / "compile.txt")
proof_flags = [
    "--mode=all",
    "--report=all",
    "--checks-as-errors=on",
    "--warnings=error",
    "--level=2",
]
result = run(
    [
        "gnatprove",
        "-P",
        project,
        "-u",
        "loam_balance_admission.adb",
        *proof_flags,
    ],
    EVIDENCE / "prove.txt",
)
summary = (WORK / "obj/gnatprove/gnatprove.out").read_text()
(EVIDENCE / "gnatprove.out").write_text(summary)

success = re.search(r"Success: all checks proved \(([1-9][0-9]*) checks\)", result.stdout)
if not success:
    raise SystemExit("Expected a non-vacuous all-checks-proved GNATprove result")
checks = int(success.group(1))
if "0 pragma Assume statements" not in summary:
    raise SystemExit("Missing zero-Assume audit in proof report")
total_line = re.search(
    r"^Total\s+\d+\s+(?:\d+\s+\(\d+%\)|\.)\s+(?:\d+\s+\(\d+%\)|\.)\s+\.\s+\.\s*$",
    summary,
    re.M,
)
if not total_line:
    raise SystemExit("Unexpected proof totals / justified / unproved report")
(EVIDENCE / "qualified-total.txt").write_text(
    f"checks={checks}\n{total_line.group(0)}\n"
)

run([WORK / "bin/loam_balance_probe_test"], EVIDENCE / "runtime.txt")

negative_control(
    "wrong-predicate",
    "update items set text='Total = 1' where type='if'",
    ("postcondition might fail",),
    proof_flags,
)
negative_control(
    "too-narrow-quantity",
    "update diagram_info set value=replace(value, 'integer Quantity -30 30', 'integer Quantity -29 29') where name='ada'",
    ("overflow check might fail", "range check might fail"),
    proof_flags,
)

print(
    "PASS: bounded LOAM balance-admission witness; "
    f"{checks} checks proved, 9,261 runtime triples, two negative proof controls"
)
