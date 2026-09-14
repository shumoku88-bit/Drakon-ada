# Phase O1: Libadalang source-observation probe

## Purpose

This probe is the first implementation checkpoint after the source-observation
pivot.  It does **not** generate DRAKON and it does **not** introduce the final
normalized control-flow graph.  It asks a smaller question first:

> Can Drakon-ada recover trustworthy, deterministic Ada/SPARK source structure
> and exact source locations from canonical source without writing an Ada parser
> of its own?

The candidate frontend is AdaCore Libadalang.

## Current probe

The repository-owned fixture is:

```text
examples/source-observation/observation_fixture.adb
```

It contains:

- straight-line assignments;
- two `if` statements;
- one `while` loop;
- one `return`;
- a `SPARK_Mode` aspect around the observed body.

Run the observer with Libadalang's Python bindings available:

```sh
python3 tools/observe_ada.py \
  examples/source-observation/observation_fixture.adb \
  --pretty
```

For an external source tree such as hra-n, the source root must be explicit so
source identity is stable and never depends on the caller's current directory:

```sh
python3 tools/observe_ada.py /path/to/hra-n/src/example.adb \
  --source-root /path/to/hra-n \
  --pretty
```

The output schema is currently:

```text
drakon-ada/source-observation/v1
```

Each observed statement carries:

- deterministic observation id within the subprogram;
- normalized coarse kind (`action`, `decision`, `loop`, `return`);
- exact Libadalang AST node kind;
- exact source span;
- source text;
- source-file SHA-256 at the document level.

No edges are emitted yet.  Edge construction belongs to Phase O2 after this
frontend boundary is shown to be reliable.

## Fail-closed behavior

The O1 observer refuses to publish an observation when:

- the source does not exist;
- the source is outside the declared source root;
- Libadalang reports parse diagnostics;
- no syntax tree is returned;
- the file does not contain exactly one `SubpBody` for this deliberately bounded
  probe;
- the observed body has no explicit source name.

Unsupported control-flow semantics are **not** silently translated into a simpler
shape.  O1 only serializes statement observations; qualification of supported vs
explicitly unsupported constructs belongs to O2.

## Tests and qualification status

`tests/test_source_observation.py` checks:

- stable source identity and source digest;
- statement-kind recovery for the fixture;
- nonempty exact source spans;
- byte-for-byte deterministic JSON output;
- parse diagnostics failing closed;
- rejection of a source outside its declared root.

Tests that require Libadalang are skipped when its Python bindings are not
installed.  This is intentional at the probe stage: Libadalang is still a
**candidate frontend, not a qualified Drakon-ada dependency**.  The historical
`tools/verify.py` gate is therefore not yet changed to require it.

Before Phase O1 can be called qualified, record a reproducible installation on
the current development platform and run the Libadalang-backed tests there.

## Frontend facts observed before adoption

Upstream Libadalang describes itself as a parsing and semantic-analysis library
for Ada and exposes Python bindings suitable for tooling.  Its current Python API
provides `AnalysisContext`, `get_from_file`, syntax-tree node classes, and
one-based source-location ranges.  Libadalang does not claim to replace GNAT's
full Ada legality checking, so compiler legality and GNATprove evidence remain
separate from source observation.

The upstream repository's `LICENSE.txt` states that Libadalang is licensed under
Apache License 2.0 with LLVM Exceptions.  Drakon-ada does not vendor Libadalang in
this checkpoint; distribution/attribution details should be reviewed again if a
binary/runtime dependency is later shipped with Drakon-ada.

## Next checkpoint

If this probe is reproduced successfully, Phase O2 should introduce the smallest
renderer-independent graph that can represent:

- entry / exit;
- straight-line action;
- decision true/false flow;
- loop body / exit / back edge;
- return;
- explicit unsupported observations.

Only after that graph is deterministic and no-silent-loss behavior is tested
should a DRAKON renderer consume it.
