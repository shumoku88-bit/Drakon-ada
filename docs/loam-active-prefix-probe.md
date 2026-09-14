# LOAM active-prefix probe (Phase A2)

Status: **qualified and promoted to canonical source**.

Canonical source:
`examples/loam-active-prefix-probe/active_prefix_fold.drn`.

## Why the distinction is earned

LOAM's `BalancedMovement.changes` is a runtime-variable-length `List`. Empty is
valid; admission accepts arbitrary runtime list lengths; production observes
length and reuses the retained representation through folds, filters, `take`,
iteration and UI. Phase A1's fixed four-slot all-used fold therefore does not by
itself qualify a faithful bounded representation.

LOAM does not have an independent semantic `Length` field. Here `Length` is an
implementation witness needed to distinguish the active prefix from unused
capacity in a fixed-capacity Ada/SPARK representation. Capacity four remains a
qualification witness, not a proposed production maximum.

## Representation

```text
Index := 1
Total := 0
      |
Index <= Length ?
      |
     yes
      v
Total := Total + Items (Index)
Index := Index + 1
      ↺
```

`Index_Type` is `0 .. 5`; array `Slot 1 .. 4` and `Active_Length 0 .. 4` are
subtypes of it. A caller cannot pass `Length > 4` without a checked failing
conversion, so the capacity boundary fails closed rather than truncating.

The postcondition explicitly enumerates Length 0 through 4. The invariant is
anchored after the loop's exit test, so it states the active-iteration fact
`Index <= Length`, index safety `Index <= 4`, and the four possible prefix sums.
The variant remains `Decreases => 5 - Index`. Empty input exits before the
invariant anchor with `Total = 0`.

No generator change was needed. Existing schema 3 already supports fixed arrays,
read-only indexed parameter access, scalar parameters/locals and restricted
scalar expressions. No records/fields, array locals, general calls, attributes,
element assignment, sentinels or allocation were added. Phase A1's canonical
source remains unchanged.

## Canonical-source promotion

The approved review `.drn` was promoted without changing semantic text,
metadata or geometry. Tests and the focused verifier now copy the checked-in
canonical source and mutate only disposable negative-control copies. The Phase
A1-based temporary materializer was retired, so production qualification does
not reconstruct the derived diagram.

## Qualification

Qualification was run both before promotion on the approved candidate and again
after tests/verifier were switched to the canonical source:

- focused generation tests: 3 passed;
- upstream graph and Ada generation: passed;
- GNATprove: 10 checks proved (Flow 3 / Provers 7);
- Assume / Justified / Unproved: 0 / 0 / 0;
- runtime: all `5 * 21^4 = 972,405` valid `(Length, Items)` inputs passed;
- full unittest: 30 passed;
- full `tools/verify.py`: passed.

The runtime oracle separately enumerates prefix sums for Length 0, 1, 2, 3 and
4. Because every four-slot array is tested at every Length, all possible inactive
tails are varied exhaustively and shown not to affect the result.

Four negative controls compile and then fail proof:

- off-by-one active bound (`Index <= Length + 1`): loop invariant failure;
- folding through capacity (`Index <= 4`): active-bound invariant failure;
- total range narrowed to `-39 .. 39`: range failure;
- prefix relation removed from the invariant: range/postcondition failure.

## Visual qualification

The first human review found `Index <= Length` crowded in the inherited `w=60`
decision diamond. Actual Mac Tk measurement with the Editor's Menlo 14 font gave
text width 120 and height 17. Applying pinned `p.measure_text` padding and
`if.fit` slope allowance gave the smallest 10-unit-grid half-size `w=80, h=20`.
The decision center remained `(180,240)` and its branch arm changed from `a=90`
to `a=70`, preserving the connected endpoint at x=330. Action geometry, trunk,
fold lane, loopback, 10/10 action clearance and Phase A1 were unchanged.

Human re-review approved decision text fit, Yes/No labels, fold action, loopback,
reading flow to End and the active-prefix meaning. Headless geometry was not used
as a substitute for GUI review.

Phase B (`MovementChange = Coordinate + Quantity` / `quantityAt`) remains out of
scope.
