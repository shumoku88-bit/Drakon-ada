# LOAM bounded-change-sequence probe

Status: **Phase A1 generator qualification in progress; not yet locally verified**.

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

## Generator pressure discovered by LOAM

Before this probe, Drakon-ada intentionally supported only:

- integer types and integer subtypes;
- scalar procedure parameters;
- simple assignment expressions;
- structured `if` and normalized loops;
- explicit loop invariant / variant metadata.

LOAM's retained change sequence is the first dogfood case that genuinely asks
for more. The branch now contains an intentionally narrow **schema 3** candidate
that adds only:

- fixed array type declarations whose index and element types were declared
  earlier;
- read-only indexing of procedure parameters known to have one of those array
  types;
- scalar local declarations.

It still rejects:

- record declarations and field access;
- array locals;
- general function calls;
- Ada attributes;
- arbitrary declarations embedded in actions;
- assignments into array elements.

The array-read validator does not simply allow `Name (...)`: the name must be an
explicit procedure parameter whose declared type is an explicit array type.
This keeps function-call syntax closed rather than turning the expression checker
into a partial Ada parser.

## Phase A1: fixed four-slot array fold

Before adding an active `Length`, isolate array indexing and local loop state with
a fixed four-element witness.

Conceptual shape:

```text
Index := 1
Remaining := 4
Total := 0
        |
+-------------------------------+
| Index <= 4 ?                  |
|   no  -> leave loop           |
|   yes                         |
|     Total := Total + Items(Index)
|     Index := Index + 1        |
|     Remaining := Remaining - 1
+-------------------------------+
        |
      End
```

The intended explicit postcondition is:

```text
Total = Items (1) + Items (2) + Items (3) + Items (4)
```

The current branch qualifies this new surface by transforming the already
qualified countdown DRAKON source **inside a test only**. That temporary test
fixture is not a canonical LOAM diagram and must not be promoted unless the
local compiler/prover run succeeds and the resulting diagram is worth looking
at.

Phase A1 should establish:

- array declaration emission;
- indexed reads but no general calls;
- scalar locals but no local arrays;
- index safety across a normalized DRAKON loop;
- initialization and termination;
- arithmetic safety for the fixed bounded representation;
- a postcondition relating the output total to all four retained inputs.

No production LOAM maximum is implied by the number four.

## Phase A2 only if A1 earns it

Add an explicit active `Length` and fold only the active prefix. This is where
Ada's finite-capacity policy becomes visible as a real boundary:

```text
Length <= Capacity
```

Values beyond `Length` must be ignored, while `Length > Capacity` must fail
closed rather than truncate.

Do not add Phase A2 until A1 has shown that the array/index/local surface is both
proof-friendly and visually useful.

## Phase B only if Phase A earns it

Add the semantic item shape:

```text
MovementChange = Coordinate + Quantity
```

Then probe one downstream operation that truly uses retained identity:
`quantityAt(QueryCoordinate)`.

That would test whether the visual form still helps once the sequence contains
meaningful coordinates, and whether record-field access is worth promoting into
the generator.

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

If Phase A1 makes the diagram noisier without improving understanding, stop and
reconsider the representation rather than growing Drakon-ada to imitate Lean's
`List` mechanically.
