# LOAM balance-admission dogfood probe

Status: **merged into `main` as the first canonical LOAM dogfood probe**.

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
Total := First + Second + Third;
      |
  Total = 0 ?
    /     \
  yes     no
   |       |
Accepted Accepted
:= True  := False
    \     /
      End
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

No Ada/SPARK generator feature is added for this probe. The generator supports
sequential action icons followed by a structured branch without modifications.

## Promotion to canonical source

The visual probe earned promotion: its diagram demonstrated clear cognitive
value in showing the explicit calculation and decision gate. The disposable
Python materializer (`tools/materialize_loam_balance_probe.py`) was deleted, and
the dedicated diagram is checked in as the canonical source:

```text
examples/loam-balance-probe/loam_balance_probe.drn
```

Tests and verification gates read this canonical `.drn` directly, without
regenerating it from an intermediate template.

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

## Verification results

Observed on the qualified Darwin x86_64 toolchain:

- GNATprove: **3 checks proved**
  - Initialization: 2 (Flow) — `Total`, `Accepted`
  - Functional contract: 1 (Prover: CVC5) — Postcondition
  - `0 pragma Assume statements`
  - 0 justified, 0 unproved
- Runtime: all `21^3 = 9,261` valid input triples exhaustively tested and passed
- Negative proof controls:
  1. `wrong-predicate` (`Total = 1` in diagram): fails with `high: postcondition might fail`
  2. `too-narrow-quantity` (`Quantity -29 .. 29`): fails with `high: range check might fail, cannot prove lower bound for First + Second + Third` on assignment to `Total`

## Focused gate

Run:

```sh
python3 tools/verify_loam_balance_probe.py
```

The gate requires:

1. focused generation tests and byte-for-byte golden output;
2. Ada compilation with assertions and overflow checking;
3. a non-vacuous GNATprove all-checks-proved result (all 3 checks);
4. zero `pragma Assume`, zero justified checks, and zero unproved checks;
5. all `21^3 = 9,261` valid input triples to agree on both `Total` and admission;
6. the wrong-predicate source mutation to fail for the expected postcondition;
7. the too-narrow integer range to fail for a range check while writing the explicit `Total`.

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
