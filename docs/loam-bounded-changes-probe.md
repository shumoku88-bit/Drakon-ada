# LOAM bounded-change-sequence probe

Status: **research boundary fixed; implementation not yet started**.

Reference LOAM commit: `d00ee74c443e53a40983195a863eb3ca6b24fcde`.
Reference Drakon-ada main after the first LOAM dogfood merge:
`c9e42609911c975d68e24c390e9561ee8de5493e`.

## Question

Does LOAM itself force Drakon-ada to represent a retained finite sequence of
changes, or would adding array/list support merely be speculative generator
growth?

The answer from current production LOAM is: **the retained sequence is real
semantic data, not just an implementation detail of the zero-total fold**.

`BalancedMovement` stores:

```text
measure
changes : List (MovementChange Coordinate)
balanced : movementTotalQuanta changes = 0
```

The first Drakon-ada probe represented only three signed quantities and the
zero-total admission gate. That was enough to test the central admission law,
but it intentionally did not retain the original change sequence.

## Why the original sequence matters downstream

Current LOAM reads `movement.changes` after admission in several independent
ways:

- `BalancedMovement.quantityAt` folds the retained changes by coordinate;
- `ScheduledReview` and `OpenScheduledCli` filter negative changes;
- `ScheduledOccurrenceConstruction.positiveTotalQuanta` folds positive-side
  quantities;
- `CapacityReview.rememberedPurposes` scans retained capacity coordinates;
- `AccountingRolePublisher` asks whether any retained change uses a locus;
- CLI/TUI surfaces iterate, map, or take prefixes of retained changes for review.

Therefore this replacement would be semantically insufficient:

```text
BalancedMovement := { Total = 0 }
```

because the original finite presentation remains observable and reusable after
admission.

## Earned requirement

An Ada/SPARK refinement of this boundary needs some representation with all of
these properties:

1. **Finite retained sequence** — accepted movement keeps the represented
   changes, not only an aggregate.
2. **Explicit active length** — no silent truncation or sentinel convention.
3. **Stable order** — later display and finite-presentation observations may
   inspect the represented order even when additive projections are order
   invariant.
4. **Indexed read access** — later folds, filters, and coordinate projections
   must be able to revisit each retained item.
5. **Fail-closed capacity boundary** — if an Ada implementation chooses a finite
   maximum, exceeding it is an explicit admission/persistence boundary, never
   silent data loss.
6. **Bounded arithmetic obligations stay visible** — a finite container must not
   hide the distinction between Lean `Int` and machine-representable totals.

A finite maximum in SPARK would be an **implementation policy**, not a claim
that LOAM's current Lean `List` has a semantic maximum.

## Current Drakon-ada gap

The current generator is intentionally much smaller than what this requires.
It currently supports:

- integer types and integer subtypes;
- scalar procedure parameters;
- simple assignment expressions;
- structured `if` and normalized loops;
- explicit loop invariant / variant metadata.

It deliberately rejects or lacks:

- array declarations;
- record declarations;
- indexed reads such as `Items (Index)`;
- record field reads such as `Change.Quantity`;
- local variable declarations;
- general function calls and Ada attributes.

This is the first LOAM dogfood result that genuinely pressures the generator
surface. The correct response is not to add all missing Ada syntax at once.

## Next falsifiable probe: Phase A

Test only the smallest new capability forced by the retained-list observation:
**a bounded sequence of signed quantities**.

The probe should use a tiny witness capacity, for example four slots, while
stating clearly that the number is experimental rather than a production LOAM
limit.

Conceptual shape:

```text
Index := 1
Total := 0
        |
   Length = 0 ? ---- yes ---> done
        |
       no
        v
+-----------------------------+
| Total := Total + Items(Index)
| Index = Length ?
|   yes -> leave loop
|   no  -> Index := Index + 1
+-----------------------------+
        |
   Total = 0 ?
     /      \
   yes      no
```

Phase A is successful only if:

- the DRAKON diagram remains easier to inspect than equivalent hand-written
  control flow;
- SPARK proves index safety, initialization, termination, arithmetic safety, and
  the explicit admission contract for the bounded representation;
- negative controls demonstrate that an off-by-one index, too-small arithmetic
  range, or weakened invariant is caught;
- generator changes remain narrow and reusable rather than becoming a general
  Ada parser.

Phase A does **not** claim to implement LOAM `MovementChange` yet.

## Phase B only if Phase A earns it

Add the semantic item shape:

```text
MovementChange = Coordinate + Quantity
```

Then probe one downstream operation that truly uses retained identity:
`quantityAt(QueryCoordinate)`.

That would test whether the visual form still helps once the sequence contains
meaningful coordinates, and whether array indexing plus record-field access are
worth promoting into the generator.

Do not add Phase B features merely because Ada supports them.

## Decision rule

Proceed by the same rule that worked for the first probe:

```text
LOAM demands a distinction
        ↓
make the smallest visual/executable witness
        ↓
look at the DRAKON diagram
        ↓
let GNATprove expose representation obligations
        ↓
promote only what survives both inspections
```

If Phase A makes the diagram noisier without improving understanding, stop and
reconsider the representation rather than growing Drakon-ada to imitate Lean's
`List` mechanically.
