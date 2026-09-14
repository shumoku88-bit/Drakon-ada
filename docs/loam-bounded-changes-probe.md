# LOAM bounded-change-sequence probe

Status: **Phase A1 qualified and promoted to canonical source**.

Canonical DRAKON source:
`examples/loam-bounded-changes-probe/array_fold.drn`.

Reference LOAM commit: `d00ee74c443e53a40983195a863eb3ca6b24fcde`.
Reference Drakon-ada main after the first LOAM dogfood merge:
`c9e42609911c975d68e24c390e9561ee8de5493e`.

## Why LOAM requires retained finite sequence data

The first dogfood probe captured only the zero-total admission law. That is not
enough to represent LOAM's `BalancedMovement`, because admitted
`BalancedMovement.changes` remains observable. LOAM later reuses the retained
finite presentation for:

- coordinate projection through `quantityAt`;
- positive/negative filtering and folding;
- `any`-style locus and purpose queries;
- persistence and scheduled/capacity review;
- CLI/TUI iteration, mapping, prefix display and human review.

Replacing the sequence with only `{ Total = 0 }` would erase stable-order data
needed by those independent consumers. The sequence requirement is therefore
earned by production semantics, not speculative generator growth.

## Phase A1 witness and earned surface

Phase A1 isolates indexed traversal from future active-length and record work:

```text
Index := 1
Total := 0
      |
  Index <= 4 ?
      |
     yes
      v
Total := Total + Items (Index)
Index := Index + 1
      ↺
```

Explicit loop variant:

```text
Decreases => 5 - Index
```

Explicit postcondition:

```text
Total = Items (1) + Items (2) + Items (3) + Items (4)
```

`Remaining` was removed because it was completely derivable as `5 - Index`.
The generator surface earned and qualified here is deliberately narrow:

- fixed array declarations whose index and element types were declared earlier;
- read-only indexed access to explicitly array-typed procedure parameters;
- scalar locals;
- scalar loop-variant expressions through the restricted expression grammar.

Array locals, general function calls, array indexing in variants, records/field
access, Ada attributes, arbitrary declarations in actions and array-element
assignment remain rejected. No generated Ada is hand-edited.

Four slots are a finite **qualification witness**, not a production capacity or
a semantic maximum for LOAM's Lean `List`.

## Canonical-source promotion

The human-approved diagram was promoted without changing semantic text,
metadata or relevant geometry. Tests and the focused verifier now copy the
checked-in canonical `.drn`; only disposable negative-control copies are
mutated. The countdown-based materializer was deleted, so the derived diagram
is no longer reconstructed during production qualification.

## Qualification result

Observed on the documented Darwin x86_64 toolchain:

- focused bounded-array unittest: 7 passed;
- upstream graph generation: passed;
- GNATprove: **10 checks proved** (Flow 3 / Provers 7);
- `pragma Assume`: 0;
- Justified: 0;
- Unproved: 0;
- exhaustive runtime: all `21^4 = 194,481` four-slot inputs passed;
- full unittest: 27 passed;
- full `tools/verify.py`: passed, including existing Movement and control-flow
  qualification.

Three negative proof controls compiled and then failed proof for the expected
reason:

- off-by-one `Items (Index + 1)`: index/invariant failure;
- `Quantity -40 .. 40` narrowed to `-39 .. 39`: range failure;
- weak invariant omitting the fold relation: range/postcondition failure.

Human visual review approved text fit, line clearance, loopback and reading
flow. See `docs/bounded-array-layout-qualification.md` for geometry evidence.

## What remains separate

Phase A2—an explicit active `Length`, active-prefix semantics and fail-closed
capacity—is an unstarted, separate research decision. Phase B—`MovementChange =
Coordinate + Quantity`, records/field access and `quantityAt`—also remains future
work. Canonicalizing Phase A1 does not authorize either expansion.
