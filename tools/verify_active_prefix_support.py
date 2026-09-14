#!/usr/bin/env python3
"""Focused proof/runtime gate for the canonical Phase-A2 active-prefix witness."""
from pathlib import Path
import os
import re
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)
WORK = ROOT / "build/active-prefix-support"
EVIDENCE = WORK / "evidence"
CANONICAL_SOURCE = ROOT / "examples/loam-active-prefix-probe/active_prefix_fold.drn"
SOURCE = WORK / "active_prefix_fold.drn"

LOOP_INVARIANT = (
    "Index >= 1 and then Index <= Length and then Index <= 4 and then "
    "((Index = 1 and then Total = 0) or else "
    "(Index = 2 and then Total = Items (1)) or else "
    "(Index = 3 and then Total = Items (1) + Items (2)) or else "
    "(Index = 4 and then Total = Items (1) + Items (2) + Items (3)))"
)
WEAK_LOOP_INVARIANT = "Index >= 1 and then Index <= Length"
PROOF_FLAGS = [
    "--mode=all", "--report=all", "--checks-as-errors=on", "--warnings=error", "--level=2"
]


def run(args, log, success=True, timeout=240):
    result = subprocess.run(
        list(map(str, args)), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout,
    )
    print(result.stdout, end="")
    Path(log).write_text(result.stdout)
    if success and result.returncode != 0:
        raise SystemExit(f"FAILED ({result.returncode}): {args}")
    return result


def generated_project(path: Path, include_main=False):
    main = '\n   for Main use ("active_prefix_fold_test.adb");' if include_main else ""
    path.write_text(
        f'''project Active_Prefix_Qualification is
   for Languages use ("Ada");
   for Source_Dirs use ("generated", ".");
   for Object_Dir use "obj";
   for Exec_Dir use "bin";{main}
   package Compiler is
      for Default_Switches ("Ada") use ("-gnat2022", "-gnata", "-gnato", "-gnatwe");
   end Compiler;
end Active_Prefix_Qualification;
'''
    )


def runtime_harness(path: Path):
    path.write_text(
        '''with Ada.Text_IO;
with Active_Prefix_Fold;

procedure Active_Prefix_Fold_Test is
   use Active_Prefix_Fold;
   Items : Change_Array;
   Total : Quantity;
   Expected : Quantity;
   Count : Natural := 0;
begin
   for A in Change_Quantity loop
      for B in Change_Quantity loop
         for C in Change_Quantity loop
            for D in Change_Quantity loop
               Items := (1 => A, 2 => B, 3 => C, 4 => D);
               for Length in Active_Length loop
                  case Length is
                     when 0 => Expected := 0;
                     when 1 => Expected := A;
                     when 2 => Expected := A + B;
                     when 3 => Expected := A + B + C;
                     when 4 => Expected := A + B + C + D;
                     when others => raise Program_Error;
                  end case;
                  Fold_Active_Prefix (Items, Length, Total);
                  if Total /= Expected then
                     raise Program_Error with "active-prefix fold mismatch";
                  end if;
                  Count := Count + 1;
               end loop;
            end loop;
         end loop;
      end loop;
   end loop;
   if Count /= 972_405 then
      raise Program_Error with "unexpected active-prefix test cardinality";
   end if;

   Ada.Text_IO.Put_Line
     ("PASS: active prefix, all 972,405 valid array/Length inputs");
end Active_Prefix_Fold_Test;
'''
    )


def mutate_metadata(source: Path, old: str, new: str):
    with sqlite3.connect(source) as db:
        value = db.execute("select value from diagram_info where name='ada'").fetchone()[0]
        if old not in value:
            raise RuntimeError(f"metadata mutation target not found: {old!r}")
        db.execute("update diagram_info set value=? where name='ada'", (value.replace(old, new),))


def mutate_condition(source: Path, text: str):
    with sqlite3.connect(source) as db:
        db.execute("update items set text=? where type='if'", (text,))


def negative_control(label, mutate, expected_diagnostics, runner):
    work = WORK / label
    work.mkdir()
    source = work / "active_prefix_fold.drn"
    shutil.copyfile(SOURCE, source)
    mutate(source)
    generated = work / "generated"
    run([*runner, source, generated], EVIDENCE / f"{label}-generate.txt")
    project = work / "active_prefix_qualification.gpr"
    generated_project(project)
    run(["gprbuild", "-p", "-c", "-P", project], EVIDENCE / f"{label}-compile.txt")
    result = run(
        ["gnatprove", "-P", project, "-u", "active_prefix_fold.adb", *PROOF_FLAGS],
        EVIDENCE / f"{label}-prove.txt", success=False,
    )
    if result.returncode == 0 or not any(d in result.stdout for d in expected_diagnostics):
        raise SystemExit(f"{label}: expected proof failure containing {expected_diagnostics!r}")


if WORK.exists():
    shutil.rmtree(WORK)
EVIDENCE.mkdir(parents=True)
for tool in (os.environ.get("TCLSH", "tclsh"), "gprbuild", "gnatprove"):
    if not shutil.which(tool):
        raise SystemExit(f"Missing {tool}; this probe is not a skipped success")

run([sys.executable, "tools/setup.py"], EVIDENCE / "setup.txt")
run(
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_active_prefix_support.py", "-v"],
    EVIDENCE / "generation-tests.txt",
)
shutil.copyfile(CANONICAL_SOURCE, SOURCE)
runner = [os.environ.get("TCLSH", "tclsh"), "integration/drakon-editor/generate.tcl"]
run([*runner, SOURCE, WORK / "generated"], EVIDENCE / "generate.txt")
runtime_harness(WORK / "active_prefix_fold_test.adb")
project = WORK / "active_prefix_qualification.gpr"
generated_project(project, include_main=True)
run(["gprbuild", "-p", "-P", project], EVIDENCE / "compile.txt")
result = run(
    ["gnatprove", "-P", project, "-u", "active_prefix_fold.adb", *PROOF_FLAGS],
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
    summary, re.M,
)
if not total_line:
    raise SystemExit("Unexpected proof totals / justified / unproved report")
(EVIDENCE / "qualified-total.txt").write_text(f"checks={checks}\n{total_line.group(0)}\n")
run([WORK / "bin/active_prefix_fold_test"], EVIDENCE / "runtime.txt", timeout=300)

negative_control(
    "off-by-one-active-bound",
    lambda source: mutate_condition(source, "Index <= Length + 1"),
    ("loop invariant might fail", "index check might fail", "postcondition might fail"),
    runner,
)
negative_control(
    "inactive-tail-folded",
    lambda source: mutate_condition(source, "Index <= 4"),
    ("loop invariant might fail", "postcondition might fail"),
    runner,
)
negative_control(
    "too-narrow-total",
    lambda source: mutate_metadata(source, "integer Quantity -40 40", "integer Quantity -39 39"),
    ("overflow check might fail", "range check might fail"),
    runner,
)
negative_control(
    "weak-invariant",
    lambda source: mutate_metadata(source, LOOP_INVARIANT, WEAK_LOOP_INVARIANT),
    ("overflow check might fail", "range check might fail", "postcondition might fail"),
    runner,
)

print(
    "PASS: Phase A2 active prefix; "
    f"{checks} checks proved, 972,405 exhaustive inputs, four negative proof controls"
)
