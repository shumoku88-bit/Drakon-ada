# Minimal structured control-flow qualification

Baseline checkpoint **`6f179ac` is unchanged**. This is the next bounded step,
not a LOAM migration and not a claim of complete Ada/SPARK language support.
The editor remains pinned to the same commit in `upstream.lock`.

## Authoritative examples

| Source | Behavior | Boundary coverage |
|---|---|---|
| `examples/control-flow/branch/branch.drn` | Absolute value for `Input : -10 .. 10`, output `Magnitude : 0 .. 10` | Both branches, zero boundary, negative/positive endpoints; all 21 inputs |
| `examples/control-flow/countdown/countdown.drn` | Initialize `Count := Amount`, repeat `Count := Count - 1` while positive; output zero | Zero, one, and multiple iterations; all 11 inputs `0 .. 10` |

These are real SQLite DRAKON documents, passed through `graph::verify_all`,
`fix_graph_for_diagram`, and `generate_functions ... nogoto=1`. Tests do not
replace upstream normalization with mocked trees or assemble the Ada body by
hand. The loop diagram uses a question and return arrow, not backward Ada goto.

Generated countdown control structure:

```ada
Count := Amount;
loop
    if Count > 0 then
        null;
    else
        exit;
    end if;
    pragma Loop_Invariant (Count > 0 and then Count <= Amount);
    pragma Loop_Variant (Decreases => Count);
    Count := Count - 1;
end loop;
```

The apparently empty positive branch is upstream's normal structured result.
Its subsequent decrement is reachable only when the condition is true. Do not
hand-simplify the generated code. This tests `if` nested within `loop`, an empty
branch (`null;`), loop exit, sequential actions, and distinct Ada block closers.

## Defects exposed by actual diagrams

The first movement implementation supplied Tcl command-prefix lists for literal
syntax callbacks. Upstream invokes `$callback`, not `{*}$callback`, so branch/loop
emission failed with e.g. `invalid command name "gen_ada::literal loop"`.
The emitter now supplies named zero-argument procedures. No upstream patch.

The conservative expression filter also rejected grouping after `or else`,
confusing it with a function call. It now allows parenthesized operands after
logical operator keywords while continuing to reject function-call escape hatches.

Neither change modifies the movement output: its original golden bytes and
three-check proof gate remain unchanged.

## Explicit loop specification: schema 2

Schema 1 remains accepted exactly as before. Schema 2 adds required fields:

```text
loop_annotations {
    9 {
        invariant {Count > 0 and then Count <= Amount}
        variant {Decreases Count}
    }
}
always_terminates True
```

- Anchor `9` refers to an existing **action icon** in the same diagram.
- Both pragmas are emitted **immediately before** that action. Placement is part
  of the explicit specification, not inferred from graph shape.
- The generator's `inspect_tree` callback verifies that the anchor survives and
  lies inside a normalized loop. Missing icons, non-action icons, duplicate
  anchors and anchors outside a loop are errors, not silently ignored metadata.
- An invariant is an explicit restricted Ada expression. A variant is currently
  one `Increases`/`Decreases` direction plus an identifier. Multi-component
  variants, inferred bounds and arbitrary annotation code are not supported.
- Explicit `always_terminates True` produces the `Always_Terminates => True`
  subprogram aspect. The SPARK profile does not infer or establish this fact;
  GNATprove must prove it. False is also a syntactically accepted explicit value,
  but makes no positive termination claim and is not the qualified example.
- No invariant/variant is universally required just because a loop exists.
  Schema 1 still permits loop generation; its actual proof/termination obligations
  must be assessed separately. The qualified countdown deliberately requests and
  checks both invariant/variant obligations and termination.

The first attempted invariant, `Count <= Amount`, was insufficient: at the
invariant cut point, GNATprove could no longer use positivity to establish the
subtraction's lower bound. `Count = 0` appeared as a counterexample. The reviewed
metadata was explicitly strengthened with `Count > 0`; the generator did not
silently derive that condition from the question icon. The weak invariant is
retained as a negative proof test.

## Results on the qualified toolchain

Full gate: `python3 tools/verify.py` (movement **plus** control flow).
Focused gate: `python3 tools/verify_control_flow.py` (deletes `build/control-flow/`).
Generation suite: `python3 -m unittest discover -s tests -v` after setup.
Clean clone: `python3 tools/check_clean.py` runs the extended full gate.

Observed control-flow proof (GNATprove FSF 16.1.0):

```text
Initialization        2    Flow 2
Run-time Checks       3    Provers 3
Assertions            2    Provers 2
Functional Contracts  2    Provers 2
Termination           2    Flow 1, Provers 1
Total                11    Flow 3 (27%), Provers 8 (73%)
Justified .    Unproved .
Analyzed 2 units; 2/2 packages/subprograms analyzed in each
0 pragma Assume statements in each analyzed entry
Success: all checks proved (11 checks).
```

The assertions are loop invariant initialization/preservation. Termination
covers the variant and explicit subprogram termination aspect. Runtime checks
include both branch result bounds and countdown subtraction bounds. Unlike the
straight-line movement, this example leaves explicit range-check obligations.
GNAT compilation uses assertions/overflow checks; runtime tests exhaust all 32
valid inputs and have a process timeout.

Generation regressions: **16 tests total** (original 9 + control-flow 7), covering
byte-identical regeneration, unchanged source hashes, both profiles, annotation
errors, metadata-only invariant changes and rejected pragma injection.

### Negative proof controls

Every mutation starts from a copied source `.drn`, regenerates, and must compile.
Generated Ada is never edited. Negative programs are not executed.

| Source mutation | Required proof failure |
|---|---|
| Branch positive action becomes `Result := 0;` | `postcondition might fail` |
| Loop action becomes `Count := Count;` | `loop variant might fail` (no progress) |
| Explicit invariant loses `Count > 0` | `range check might fail` |

The original faulty-movement control is still required as well. Nonzero status
alone is insufficient: the expected diagnostic must be present. Main proof gates
require nonempty exact totals, no justifications/unproved checks, and no Assume
statements; tool/report upgrades require deliberate review.

The extended full gate and disposable clean Git clone gate both passed. The
clone fetched upstream anew and remained Git-clean after generation, proof and
runtime tests; it reused the installed PATH toolchain. Baseline `6f179ac` remains
the first checkpoint; this step forms the separate second checkpoint,
“Basic structured control flow established”.

Raw logs: `build/control-flow/evidence/`; overall logs: `build/evidence/`.

## Qualified scope and remaining limits

This completes the **minimal** sequence → two-way branch → repeated loop/exit
cycle, including a condition inside a loop and explicit termination evidence.
It does not prove the generator correct for every DRAKON graph. Arbitrary nested
loops, nested application branches, multiple exits, post-test loops, native
foreach, select/case lowering and graph shapes requiring fallback are not yet
qualified. Unstructured fallback still fails closed; no forward/backward goto
has been added. Annotation anchors may need redesign for richer transformations.

GUI editing/metadata save-reopen remains untested. Evidence uses the existing
Darwin x86_64 toolchain, not a newly installed OS image. LOAM remains a possible
future consumer, not a dependency or a migration target in this step.
