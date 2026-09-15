# DRAKON SQLite writer (Phase O3b)

Phase O3b turns the renderer-independent O3a projection into a real DRAKON
Editor `.drn` document.

The authority boundary does not change:

```text
Ada/SPARK source
  -> normalized control-flow observation
  -> DRAKON projection
  -> .drn SQLite rendering
```

The writer is a storage/geometry renderer. It never reads Ada source, imports
Libadalang, or reconstructs semantic control flow from source text.

## Input and output

`tools/write_drakon.py` accepts
`drakon-ada/drakon-projection/v1` JSON and writes a DRAKON Editor SQLite file
with the pinned upstream schema:

- `info`
- `diagrams`
- `state`
- `items`
- `diagram_info`
- `tree_nodes`

The file signature uses DRAKON format version 2 and `language=SPARK`, matching
the repository's qualified DRAKON documents.

Each output contains one `diagram_info` value named
`drakon-ada/drn-projection-map/v1`. It preserves the input source identity,
subprogram identity, normalized edge roles, source trace, and the exact
projected-node to SQLite-item mapping. The `.drn` therefore remains a derived
observation rather than a second source of program truth.

## Physical layout

O3a ranks and lanes are semantic-independent layout hints. O3b is allowed to
refine them only for drawing.

The first qualified renderer uses these mechanical rules:

1. Main continuation icons stay on the main vertical.
2. A loop continuation is moved below the complete loop body before physical
   coordinates are assigned.
3. Right-hand `true` and `loop_body` regions receive reusable branch lanes.
   Overlapping live intervals cannot share a lane; completed regions can.
4. Later/nested live intervals receive inner lanes first, so enclosing bypass
   paths remain outside them.
5. The DRAKON `if` item's intrinsic right arm represents `true` or
   `loop_body`; `b=0` keeps the standard YES-right / NO-down orientation.
6. Forward joins use Manhattan vertical/horizontal connectors.
7. A normalized `back` edge is rendered by the upstream DRAKON `arrow` item,
   not by changing or reversing the semantic edge.

For the O2 qualification fixture this deliberately produces:

- outer decision bypass on physical lane 2,
- loop body on physical lane 1,
- reuse of lane 1 by the later decision after the loop has merged,
- a continuation below the full loop body,
- one standard return arrow for the loop back edge.

## Fail-closed boundary

The first O3b slice intentionally refuses shapes that need a richer physical
layout policy:

- detached/unreachable projection nodes,
- a branch source nested inside another branch region,
- overlapping branch regions that cannot be represented by the current
  structured-lane rules,
- malformed role contracts,
- a back edge that does not target a normalized loop.

O3a continues to preserve detached source nodes explicitly. O3b does not hide
them; it refuses to claim that one connected DRAKON diagram represents them.

## Qualification

Focused Python tests:

```sh
python -m unittest discover -s tests -p 'test_drakon_writer.py' -v
```

The pull-request workflow also:

1. builds a `.drn` from the frozen derived O3a fixture,
2. fetches the exact editor commit in `upstream.lock`,
3. opens the generated SQLite document through the upstream model,
4. runs upstream `graph::verify_all`,
5. fails if the pinned editor reports any graph error.

`integration/drakon-editor/verify_projection.tcl` is verification-only. It
does not invoke the suspended DRAKON-to-Ada generator lane.

The frozen JSON fixture under `examples/drakon-projection/` is a derived test
artifact. It is not authoritative source.

## O3c geometry separation and semantic round-trip

A human inspection of the first generated fixture exposed a visual ambiguity:
the loop-return bottom segment and an unrelated branch merge could occupy the
same horizontal corridor. Although upstream accepted the graph, the picture
made two independent control paths look connected.

O3c keeps the semantic projection unchanged and tightens the physical renderer:

- branch merges use a corridor close to their target icon,
- loop-return bottoms use a separate corridor close to the loop-body tail,
- unrelated horizontal routes may not overlap or touch on the same Y
  coordinate,
- a branch merge may not share a horizontal segment with the top or bottom of
  a DRAKON return arrow.

The writer fails closed if those geometric separation rules cannot be met.

Qualification now also checks semantic round-trip against the pinned DRAKON
Editor interpretation. After `graph::verify_all`, the verifier reads upstream's
in-memory `links` graph, collapses line/joint vertices until the next mapped
semantic icon, reconstructs normalized edge roles, and compares the result with
the projection map embedded in the `.drn`.

The role reconstruction is mechanical:

- decision: down=`false`, right=`true`,
- loop: down=`loop_exit`, right=`loop_body`,
- action: forward=`next`, rank-decreasing edge=`back`,
- return=`return`,
- entry=`next`.

This is deliberately not source regeneration. Ada/SPARK remains authoritative;
the check only proves that the derived DRAKON geometry is interpreted by the
pinned editor as the same normalized control-flow graph that entered the
writer.
