# Phase O2: normalized control-flow observation

## Purpose

Phase O2 turns the Phase O1 statement inventory into a small renderer-independent
control-flow graph. DRAKON is still downstream. The graph must be useful without
DRAKON and must never hide source constructs merely to obtain a prettier diagram.

The output schema is:

```text
drakon-ada/control-flow-observation/v1
```

The document contains stable source identity plus:

```text
entry_node
exit_node
nodes[]
edges[]
```

Source-backed nodes retain their Ada AST kind, exact statement span and source
text. Decisions and loops additionally retain the exact condition text and
condition span. Synthetic entry/exit nodes are explicitly marked as synthetic and
anchored to the observed subprogram span.

## Qualified semantic slice

This checkpoint deliberately supports only the structured constructs needed by
the repository fixture:

- assignment, call and null statements as straight-line actions;
- `if` / `else` without `elsif`;
- `while` loops;
- `return`.

Initial edge roles are:

- `next`;
- `true` / `false`;
- `loop_body` / `loop_exit` / `back`;
- `return`.

The fixture therefore produces a real graph with a loop back edge and a return
edge to the synthetic exit node. Node ids are allocated deterministically in
source preorder and edges are sorted deterministically after construction.

## No-silent-loss boundary

A syntactically valid Ada construct outside this qualified slice is not flattened
into an `action` node. The observer refuses the projection instead.

Examples currently rejected include:

- `elsif`;
- `case` and other unqualified statement kinds;
- exception handlers;
- `finally` blocks;
- other loop forms until their exact semantics are added deliberately.

This is intentionally conservative. When hra-n exposes a required construct, add
that distinction because a real observed program needs it, then extend tests and
the renderer-independent model before teaching the DRAKON renderer about it.

## Graph construction

The source frontend remains Libadalang. Phase O2 does not implement a second Ada
parser.

The builder first walks only direct statement lists and registers supported nodes
in source preorder. It then constructs structured edges toward an explicit
continuation:

- ordinary actions fall through to the next node;
- decisions connect true/false branches to their branch entries or continuation;
- a while condition connects to the body and loop exit;
- normal completion of the while body returns through a `back` edge;
- return connects directly to the synthetic exit and has no fallthrough edge.

This makes the normalized graph independent of DRAKON SQLite ids, coordinates,
branch orientation or drawing layout.

## Run

With Libadalang's Python bindings available:

```sh
python3 tools/observe_ada.py \
  examples/source-observation/observation_fixture.adb \
  --pretty
```

The Phase O1 source-root and charset boundaries remain unchanged.

## Tests

`tests/test_source_observation.py` now checks:

- exact deterministic node order for the fixture;
- exact expected edge relation;
- decision and loop condition labels;
- source spans and source digest;
- byte-for-byte deterministic JSON;
- parse diagnostics failing closed;
- rejection of `case` as unqualified control flow;
- rejection of exception handlers;
- source-root rejection before frontend use.

Libadalang-backed tests still skip when the Python bindings are unavailable. This
PR establishes the graph semantics but does not yet claim Libadalang as a
qualified mandatory dependency on the development platform.

## Next checkpoint

Before Phase O3 DRAKON rendering, reproduce this graph with Libadalang installed
on the development machine and inspect the emitted JSON directly. Once that
frontier is confirmed, the first renderer should consume only this graph and
source identity. It must not reparse Ada or invent a second control-flow model.
