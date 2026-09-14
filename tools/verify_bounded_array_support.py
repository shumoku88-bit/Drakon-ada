#!/usr/bin/env python3
"""Focused Phase-A1 gate for the temporary bounded-array DRAKON witness."""
from pathlib import Path
import os
import re
import shutil
import sqlite3
import subprocess
import sys

from tools.bounded_array_fixture import LOOP_INVARIANT, WEAK_LOOP_INVARIANT, materialize

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
WORK = ROOT / "build/bounded-array-support"
EVIDENCE = WORK / "evidence"
SOURCE = WORK / "array_fold.drn"

PROOF_FLAGS = [
    "--mode=all",
    "--report=all",
    "--checks-as-errors=on",
    "--warnings=error",
    "--level=2",
]


def run(args, log, success=True, timeout=180):
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


def generated_project(path: Path, include_main=False):
    main = '\n   for Main use ("array_fold_test.adb");' if include_main else ""
    path.write_text(
        f'''project Array_Fold_Qualification is
   for Languages use ("Ada");
   for Source_Dirs use ("generated", ".");
   for Object_Dir use "obj";
   for Exec_Dir use "bin";{main}
   package Compiler is
      for Default_Switches ("Ada") use ("-gnat2022", "-gnata", "-gnato", "-gnatwe");
   end Compiler;
end Array_Fold_Qualification;
'''
    )


def runtime_harness(path: Path):
    path.write_text(
        '''with Ada.Text_IO;
with Array_Fold;

procedure Array_Fold_Test is
   use type Array_Fold.Quantity;
   Items : Array_Fold.Change_Array;
   Total : Array_Fold.Quantity;
   Count : Natural := 0;
begin
   for A in Array_Fold.Change_Quantity loop
      for B in Array_Fold.Change_Quantity loop
         for C in Array_Fold.Change_Quantity loop
            for D in Array_Fold.Change_Quantity loop
               Items := (1 => A, 2 => B, 3 => C, 4 => D);
               Array_Fold.Fold_Four (Items, Total);
               if Total /= A + B + C + D then
                  raise Program_Error with "bounded array fold mismatch";
               end if;
               Count := Count + 1;
            end loop;
         end loop;
      end loop;
   end loop;
   if Count /= 194_481 then
      raise Program_Error with "unexpected bounded-array test cardinality";
   end if;
   Ada.Text_IO.Put_Line
     ("PASS: bounded array fold, all 194,481 four-slot inputs");
end Array_Fold_Test;
'''
    )


def mutate_metadata(source: Path, old: str, new: str):
    with sqlite3.connect(source) as db:
        value = db.execute("select value from diagram_info where name='ada'").fetchone()[0]
        if old not in value:
            raise RuntimeError(f"metadata mutation target not found: {old!r}")
        db.execute(
            "update diagram_info set value=? where name='ada'", (value.replace(old, new),)
        )


def negative_control(label, mutate, expected_diagnostics, runner):
    work = WORK / label
    work.mkdir()
    source = work / "array_fold.drn"
    shutil.copyfile(SOURCE, source)
    mutate(source)
    generated = work / "generated"
    run([*runner, source, generated], EVIDENCE / f"{label}-generate.txt")
    project = work / "negative.gpr"
    generated_project(project)
    run(["gprbuild", "-p", "-c", "-P", project], EVIDENCE / f"{label}-compile.txt")
    result = run(
        ["gnatprove", "-P", project, "-u", "array_fold.adb", *PROOF_FLAGS],
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
        "test_bounded_array_support.py",
        "-v",
    ],
    EVIDENCE / "generation-tests.txt",
)

materialize(SOURCE)
runner = [
    os.environ.get("TCLSH", "tclsh"),
    "integration/drakon-editor/generate.tcl",
]
run([*runner, SOURCE, WORK / "generated"], EVIDENCE / "generate.txt")

runtime_harness(WORK / "array_fold_test.adb")
project = WORK / "array_fold.gpr"
generated_project(project, include_main=True)
run(["gprbuild", "-p", "-P", project], EVIDENCE / "compile.txt")

result = run(
    ["gnatprove", "-P", project, "-u", "array_fold.adb", *PROOF_FLAGS],
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

run([WORK / "bin/array_fold_test"], EVIDENCE / "runtime.txt", timeout=180)


def off_by_one(source):
    with sqlite3.connect(source) as db:
        db.execute(
            "update items set text=replace(text, 'Items (Index)', 'Items (Index + 1)') "
            "where type='action'"
        )


def too_narrow(source):
    mutate_metadata(source, "integer Quantity -40 40", "integer Quantity -39 39")


def weak_invariant(source):
    mutate_metadata(source, LOOP_INVARIANT, WEAK_LOOP_INVARIANT)


negative_control(
    "off-by-one-index",
    off_by_one,
    ("index check might fail", "range check might fail"),
    runner,
)
negative_control(
    "too-narrow-quantity",
    too_narrow,
    ("overflow check might fail", "range check might fail"),
    runner,
)
negative_control(
    "weak-invariant",
    weak_invariant,
    ("overflow check might fail", "range check might fail", "postcondition might fail"),
    runner,
)

print(
    "PASS: Phase A1 bounded array fold; "
    f"{checks} checks proved, 194,481 runtime inputs, three negative proof controls"
)
