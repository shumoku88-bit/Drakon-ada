# Canonical bounded-array layout qualification

Status: **human visual review approved; full Phase A1 qualification passed**.

Canonical source:
`examples/loam-bounded-changes-probe/array_fold.drn`.

The canonical file is byte-copied from the approved Phase A1 review diagram.
Before promotion, its semantic item text, `diagram_info` metadata and item
geometry were compared with a freshly materialized fixture and matched. After
promotion, the same fields were compared directly with the preserved approved
file and matched. Neither canonical countdown nor pinned upstream was changed.

## GUI geometry

The first headless-sized review failed visually: the fold text overflowed its
box and crossed the loopback. The pinned upstream test dummy uses 6 units per
character; it does not measure the actual Mac Tk font.

The review diagram was opened in the actual DRAKON Editor and **Edit > Tidy up**
was invoked. The editor persists the operation directly to SQLite. A separate
SQLite connection then observed:

```text
Index := 1;\nTotal := 0;                              w=60  h=30
Total := Total + Items (Index);\nIndex := Index + 1;   w=140 h=30
```

These are half-extents in `items.w/h`. Semantic item text and metadata were
unchanged by GUI fitting.

Final canonical layout:

- main trunk: x=180;
- initialization action: center (180, 130), w=60, h=30;
- fold action: center (330, 300), w=140, h=30, bounds x=190..470;
- fold vertical: x=330, y=240..360;
- if right junction: (330, 240), a=90;
- loopback: x=480, y=180..360, w=300, a=150;
- upper return: (180, 180); lower entry: (330, 360);
- corridor width: 300; left/right action clearance: 10/10.

Width 300 is the smallest 10-unit-grid corridor containing the 280-unit action
width plus 10 units on each side. The main trunk remains fixed and connected
junction/arrow endpoints move together. Human review approved text fit, both
clearances, the loopback and the visual reading flow.

## Headless boundary

The deterministic pinned headless path remains a separate regression:

- initialization action: `(50, 30)`;
- fold action: `(110, 30)`.

Those values test dummy `measure_text -> p.measure_text -> action.fit`
semantics. They are not canonical GUI dimensions and never rewrite the checked-in
source. Tests separately assert the canonical GUI geometry and run upstream
graph verification/generation.

## Qualification

On the documented local Darwin x86_64 toolchain:

- focused unittest: 7 passed;
- focused graph/Ada generation: passed;
- GNATprove: 10 checks, Flow 3 / Provers 7;
- Assume / Justified / Unproved: 0 / 0 / 0;
- exhaustive runtime: all 194,481 inputs passed;
- off-by-one, too-narrow Quantity and weak-invariant negative controls exposed
  the expected proof failures;
- full unittest: 27 passed;
- full `tools/verify.py`: passed.

Four slots are a qualification witness, not production capacity. Active
`Length` belongs to the separate, unstarted Phase A2.
