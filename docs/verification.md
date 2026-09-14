# Movement verification checkpoint

Qualified environment and reproduction commands: [reproduction.md](reproduction.md).
Upstream commit: `a22609c4e5b1766c953cbfa2fa2234e69e38f9bd`.

| Criterion | Observed result |
|---|---|
| Regenerate from DRAKON source | PASS; byte-identical repeated output, source hash unchanged |
| No generated-code hand edits | PASS; body comes from normalized graph, specification from metadata |
| GNAT compilation | PASS; GNAT 16.1.0, assertions/overflow checks enabled |
| No unproved target checks | PASS; 3 checks: 2 initialization, 1 functional contract |
| No assumptions/suppressions/justifications | PASS for this generated target; zero Assume statements, justified column empty |
| Runtime test | PASS; all 1,000,000 valid Amount values |
| Clean checkout reproduction | PASS; disposable clean Git clone, fresh upstream fetch, full gate, clean Git status; installed PATH toolchain reused |

Generation suite: **9 tests passed**.

GNATprove command (FSF 16.1.0):

```sh
gnatprove -P examples/movement/movement.gpr -u movement.adb \
  --mode=all --report=all --checks-as-errors=on --warnings=error --level=2
```

Observed summary:

```text
Initialization        2   Flow: 2
Functional Contracts  1   Provers: 1 (CVC5)
Total                 3   Flow: 2 (67%)   Provers: 1 (33%)
Justified: .   Unproved: .
Analyzed 1 unit
Movement: 2 subprograms and packages out of 2 analyzed
0 errors, 0 warnings and 0 pragma Assume statements
Success: all checks proved (3 checks).
```

`Run-time Checks` is `.` in this report. The simple bounded arithmetic did not
leave separate run-time proof obligations; do not report fictitious overflow VC
counts. The full target is analyzed with `--mode=all`. GNAT compilation and the
runtime driver also keep checks enabled. This evidence is for the declared input
subtype, not for parsing or accepting arbitrary external integers.

## Negative proof control

Change only diagram action 4 to `Source := Amount;`, regenerate, and compile:
compilation succeeds. Proof then exits nonzero with:

```text
high: postcondition might fail, cannot prove Source = -Amount
  e.g. when Amount = 1 and Source = 1
gnatprove: unproved check messages considered as errors
```

The semantic contract did not follow the faulty implementation. The complete
verification script requires this failure and rejects an unrelated compile error
as a substitute.

## Remaining limits

- Full upstream unit/regeneration suites fail independently at the pin; detailed
  failures are recorded in [upstream-audit.md](upstream-audit.md).
- Movement is straight-line. Structured if/loop callbacks exist, but general
  if/loop generation and invariant/termination metadata are not qualified here.
- GUI editing/metadata round-trip has not been tested.
- Clean checkout uses a preinstalled toolchain; clean-machine installation,
  other operating systems, and hosted CI are not qualified.
- New work is MIT-licensed after the [fixed-commit audit](licensing.md).
  Public GitHub remote/push remains outside this local checkpoint.
- Generator correctness in general has not been formally proved. GNATprove
  verifies this generated program, not the generator or DRAKON semantics.
