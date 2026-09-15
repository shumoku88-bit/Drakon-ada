# DRAKON projection boundary

Phase O3 starts by separating **semantic observation** from **editor storage**.

The active pipeline is:

```text
Ada/SPARK source
    ↓ Libadalang
normalized control-flow observation
    ↓ tools/project_drakon.py
DRAKON projection model
    ↓ later O3b writer
DRAKON Editor .drn
```

`tools/project_drakon.py` consumes only
`drakon-ada/control-flow-observation/v1` JSON. It does not import Libadalang,
open Ada source, or rebuild control flow. That boundary is deliberate: source
parsing belongs to O2; O3 is a deterministic projection of already-normalized
facts.

## Projection schema

The current output schema is:

```text
drakon-ada/drakon-projection/v1
```

Each projected node carries:

- the normalized node id and semantic kind;
- a DRAKON-oriented icon kind (`beginend`, `action`, or `if`);
- display text;
- exact source trace data for source-backed nodes;
- deterministic rank/lane coordinates;
- an explicit `reachable` flag.

Edges retain the normalized role unchanged. Back edges remain explicit and are
marked `back: true`; the renderer does not infer loops from geometry.

The qualified O2 slice maps as follows:

| normalized kind | projection icon |
|---|---|
| `entry` / `exit` | `beginend` |
| `action` | `action` |
| `decision` | `if` |
| `loop` | `if` |
| `return` | `action` |

The `semantic_kind` remains present even where multiple normalized kinds share
the same editor icon. DRAKON drawing convenience must not erase semantic
distinctions.

## Deterministic layout

`structured-lanes/v1` removes `back` edges, checks that the remaining graph is
acyclic, and assigns ranks from the synthetic entry. A `true` or `loop_body`
edge opens one lane to the right; ordinary continuation, false/exit, and return
edges stay in the current lane. Merge points choose the leftmost incoming lane.

This is intentionally mechanical, not a claim of optimal DRAKON layout. O3b may
translate these hints into editor geometry without changing the normalized
semantics.

Source nodes not reachable from the synthetic entry are **not discarded**.
They are retained in a detached lane with `reachable: false`, so source after an
unconditional return remains visible instead of being silently simplified away.

## Fail-closed rules

Projection rejects:

- a schema other than O2 `v1`;
- incomplete observations;
- unknown node kinds or edge roles;
- dangling or duplicate edges;
- malformed entry, exit, decision, loop, return, or action edge contracts;
- loops without an explicit normalized `back` edge;
- forward cycles that are not represented by `back`.

These checks qualify the projection boundary only. They do not claim Ada
legality, proof, runtime correctness, or complete DRAKON Editor compatibility.

## Current limit

O3a intentionally does **not** write SQLite `.drn` files yet. The repository
already pins DRAKON Editor and documents its SQLite schema, but editor storage
and geometry are a separate concern. O3b should be a thin writer from this
projection model, not another parser or CFG engine.
