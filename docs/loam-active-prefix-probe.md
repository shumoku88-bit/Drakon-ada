# LOAM active-prefix probe (Phase A2 candidate)

Status: **temporary candidate technically qualified; awaiting human visual review**.

This is not a canonical source. Regenerate the review file with:

```sh
python3 tools/active_prefix_fixture.py \
  build/active-prefix-support/visual-review/active_prefix_fold.drn
```

Review path:
`build/active-prefix-support/visual-review/active_prefix_fold.drn`.

## Why the distinction is earned

LOAM's `BalancedMovement.changes` is a runtime-variable-length `List`. Empty is
valid; admission accepts arbitrary runtime list lengths; production observes
length and reuses the retained representation through folds, filters, `take`,
iteration and UI. Phase A1's fixed four-slot all-used fold therefore does not by
itself qualify a faithful bounded representation.

LOAM does not have an independent semantic `Length` field. Here `Length` is an
implementation witness needed to distinguish the active prefix from unused
capacity in a fixed-capacity Ada/SPARK representation. Capacity four remains a
qualification bound, not a proposed production maximum.

## Representation

The Phase A1 canonical source is copied into a disposable candidate and only its
identity, condition and explicit Ada metadata are changed:

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

`Index_Type` is `0 .. 5`; both array `Slot 1 .. 4` and `Active_Length 0 .. 4`
are subtypes of it. A caller cannot pass `Length > 4` without a checked failing
conversion, so the capacity boundary fails closed rather than truncating.

The postcondition explicitly enumerates Length 0 through 4. The invariant is
anchored after the loop's exit test, so it states the active-iteration fact
`Index <= Length`, index safety `Index <= 4`, and the four possible prefix sums.
The variant remains `Decreases => 5 - Index`. Empty input exits before the
invariant anchor with `Total = 0`.

No generator change was needed. Existing schema 3 already supports everything
used: fixed arrays, read-only indexed parameter access, scalar parameters and
locals, and restricted scalar expressions. No records/fields, array locals,
general calls, attributes, element assignment, sentinels or allocation were
added.

## Focused technical qualification

On the documented Darwin x86_64 toolchain:

- focused generation tests: 3 passed;
- upstream graph and Ada generation: passed;
- GNATprove: 10 checks proved (Flow 3 / Provers 7);
- Assume / Justified / Unproved: 0 / 0 / 0;
- runtime: all `5 * 21^4 = 972,405` valid `(Length, Items)` inputs passed.

The runtime oracle separately enumerates prefix sums for Length 0, 1, 2, 3 and
4. Because every four-slot array is tested at every Length, all possible inactive
tails are varied exhaustively and shown not to affect the result.

Four negative controls compile and then fail proof:

- off-by-one active bound (`Index <= Length + 1`): loop invariant failure;
- folding through capacity (`Index <= 4`): active-bound invariant failure;
- total range narrowed to `-39 .. 39`: range failure;
- prefix relation removed from the invariant: range/postcondition failure.

## Visual boundary and stop rule

The candidate retains Phase A1's actual GUI-fitted action dimensions and 10/10
corridor clearance. Running **Edit > Tidy up** in the Mac DRAKON Editor left the
candidate geometry unchanged, including the `Index <= Length` decision at
`w=60, h=20`. Headless geometry is not used as visual evidence.

Human review must now judge text fit, loopback, readability of the Length
condition, reading flow and whether the active-prefix distinction repays its
cognitive cost. Do not promote this file to canonical source or run final full
qualification until that review is approved. If the distinction makes the
DRAKON view materially worse, stop rather than expanding the generator.

Phase B (`MovementChange = Coordinate + Quantity` / `quantityAt`) is out of
scope.
