# LOAM balance-admission dogfood probe

Status: **experimental, not a LOAM migration and not yet a qualified checkpoint**.

This probe asks one narrow question: can the existing DRAKON → Ada/SPARK path
make the admission shape of LOAM's `BalancedMovement` easier to see without
adding a second semantic engine or expanding the generator first?

Reference LOAM commit: `d00ee74c443e53a40983195a863eb3ca6b24fcde`.
The relevant current definitions are `Loam/Core/Quantity.lean` and
`Loam/Core/BalancedMovement.lean`.

## What the LOAM definition says

For one caller-chosen coordinate type and one explicit measure, LOAM retains a
list of signed `MovementChange` values. `movementTotalQuanta` folds the quantities
with exact integer addition. `BalancedMovement.ofChanges?` admits the represented
movement exactly when that total is zero; an admitted value retains the measure,
original change list, and proof of balance.

The coordinate identity does not participate in the **complete-total admission
predicate**. It matters later for coordinate-wise projection. That lets this
first probe isolate the zero-total gate without pretending that coordinate or
measure evidence has disappeared from LOAM itself.

## The bounded three-change witness

The probe deliberately fixes the list length at three and gives each signed
change the small range `-10 .. 10`:

```text
First + Second + Third = 0 ?
        /          \
      yes          no
       |            |
Total := sum      Total := sum
Accepted := True Accepted := False
```

The explicit SPARK contract separately states both the materialized total and the
admission result:

```text
Total = First + Second + Third
and then
Accepted = (Total = 0)
```

`Quantity` is deliberately bounded to `-30 .. 30`, so every represented total of
three admissible inputs fits. This is an executable refinement of a **finite
witness**, not an assertion that Ada's bounded integer is equivalent to Lean's
unbounded `Int`.

No Ada/SPARK generator feature is added for this probe. The existing qualified
branch diagram supplies the already-tested DRAKON if/else geometry. The
materializer changes only its synthetic diagram name/start label, condition,
actions, and explicit Ada metadata in a disposable copy under `build/`.

Materialize a diagram that can be opened in DRAKON Editor:

```sh
python3 tools/materialize_loam_balance_probe.py
```

The resulting file is:

```text
build/loam-balance-probe/loam_balance_probe.drn
```

This generated `.drn` is **not yet a new canonical source**. The point of this
step is to decide whether the visual representation earns promotion. If it does,
promote a reviewed dedicated `.drn` in a later step rather than silently making
the Python materializer a second diagram language.

## What is preserved, and what is not

Preserved by this probe:

- signed exact arithmetic within the explicitly bounded domain;
- an explicit materialized total for the three represented changes;
- admission iff that materialized total is zero;
- an explicit contract independent from the control-flow diagram;
- no debit/credit, account, purpose, or transaction-kind semantics;
- fail-closed generation and ordinary GNATprove obligations.

Not represented yet:

- arbitrary list length;
- coordinate values or coordinate-wise projection;
- `MeasureId` as retained data;
- the original list as a returned value;
- a proof-carrying `BalancedMovement` record;
- Lean's unbounded integer semantics.

Therefore this is **not** an Ada port of `BalancedMovement.ofChanges?`. It is a
small falsifiable witness for the central admission law and the prior
`movementTotalQuanta` step.

## What the first focused run taught us

The first focused run proved the original direct-predicate program completely:

- exact total: **2 checks**;
- initialization: 1/1 proved;
- functional contract: 1/1 proved;
- `pragma Assume`: 0;
- justified: 0;
- unproved: 0;
- all `21^3 = 9,261` runtime triples passed;
- the wrong-predicate negative control failed on the postcondition as intended.

However, the original `too-narrow-quantity` control unexpectedly still proved all
2 checks after changing `Quantity` from `-30 .. 30` to `-29 .. 29`.

That was not a GNATprove defect. The expression
`First + Second + Third = 0` was evaluated in the integer type's base range, and
its result was only compared with zero. No value `30` was assigned or converted
to the first subtype `Quantity`, so there was no first-subtype range check to
fail.

This failure sharpened the probe rather than weakening it. LOAM explicitly
computes `movementTotalQuanta` before testing balance, so the revised SPARK
witness now exposes `Total : out Quantity` and assigns the sum to it on every
path. This makes the finite representation boundary observable in the program
itself.

The revised negative control still changes only `Quantity` from `-30 .. 30` to
`-29 .. 29`. With explicit `Total`, the edge `10 + 10 + 10 = 30` must now create
a range/overflow proof obligation when stored as `Quantity`.

This is the first important semantic difference from LOAM's `Quantity`, which
wraps Lean `Int`. Drakon-ada must never hide that difference behind a successful
code-generation step.

The other negative control changes the DRAKON condition to
`First + Second - Third = 0` while leaving the explicit postcondition unchanged.
Compilation must succeed and proof must fail on the postcondition. This checks
that the contract is not inferred from, or rewritten to match, the diagram.

## Focused gate

Run:

```sh
python3 tools/verify_loam_balance_probe.py
```

The gate requires:

1. focused generation tests and byte-for-byte golden output;
2. Ada compilation with assertions and overflow checking;
3. a non-vacuous GNATprove all-checks-proved result;
4. zero `pragma Assume`, zero justified checks, and zero unproved checks;
5. all `21^3 = 9,261` valid input triples to agree on both `Total` and admission;
6. the wrong-predicate source mutation to fail for the expected postcondition;
7. the too-narrow integer range to fail for an overflow/range check while writing
   the explicit `Total`.

The script records the observed check count in
`build/loam-balance-probe/evidence/qualified-total.txt`. This document does not
invent the revised count before the qualified toolchain has actually run it.

## What this is testing about DRAKON

The Lean definition is excellent at saying **what is true** about an admitted
value. The DRAKON diagram makes a different thing visible: a bounded total is
materialized and then the candidate is admitted or rejected through one explicit
gate.

The useful comparison is therefore not "which language is shorter?" but:

```text
Lean       : what proposition is retained and reusable?
DRAKON     : what path computes and admits/rejects the candidate?
SPARK      : is this bounded executable path safe and contract-correct?
```

If this view is useful after opening the generated diagram, the next real
question is whether Drakon-ada should learn a small bounded-sequence type so the
same gate can be exercised over variable-length input. If the diagram adds no
clarity, stop here; no generator feature is earned merely to resemble LOAM.
