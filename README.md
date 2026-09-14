# Drakon-ada

Drakon-ada is an Ada/SPARK **control-flow observation tool**.

Its active direction is to read real Ada/SPARK source, derive an explicit normalized
control-flow model, and project that model into DRAKON so that humans and AI can
inspect the shape of an implementation without making the diagram a second source
of truth.

## Project boundary

- **Ada/SPARK source is the source of truth.**
- DRAKON diagrams are derived observation artifacts. Regenerate them from source;
  do not hand-edit them as an alternative program representation.
- The projection must preserve source traceability. Every projected control-flow
  node must be attributable to an exact source construct/span.
- Unsupported or ambiguous source constructs must fail closed or be rendered as
  explicit unsupported observations. They must never disappear silently.
- A machine-readable observation artifact belongs beside the visual projection so
  that humans and AI can inspect the same graph precisely.
- Contracts, legality, and proof facts are not inferred from diagram shape.
  Native Ada/SPARK tooling remains authoritative for compilation and proof.
- `hra-n` is the first intended practical observation target. It is an external
  codebase, not a dependency and must not be vendored into this repository.

The intended loop is:

```text
Ada / SPARK source
        |
        v
parser / semantic frontend
        |
        v
normalized control-flow observation
       / \
      v   v
 DRAKON   machine-readable sidecar
      \   /
       v v
 human + AI inspection
        |
        v
edit Ada / SPARK source
        |
        v
compiler / tests / GNATprove
```

See [Observation architecture](docs/observation-architecture.md).

## Why DRAKON

DRAKON is used here as a visual lens over the implementation. The goal is not to
replace source-code review, tests, contracts, or proof. The goal is to expose
structural facts that are easy to miss in text alone: branch asymmetry, repeated
decisions, long exceptional paths, tangled loops, and responsibility changes
inside one routine.

A useful observation should let a reviewer move in both directions:

```text
source span -> observation node -> DRAKON shape
DRAKON shape -> observation node -> exact source span
```

## Active milestones

1. **Source observation frontier**: parse one real Ada/SPARK procedure and retain
   exact source identity for straight-line statements, `if` branches, and loops.
2. **Normalized control-flow model**: emit a deterministic machine-readable graph
   independent of DRAKON file layout.
3. **DRAKON projection**: render that graph without adding semantic distinctions
   that are absent from source.
4. **hra-n design inspection**: use the projection on a real development slice and
   record at least one concrete design finding that can be traced back to source.
5. **Optional evidence overlays**: only after the source projection is trustworthy,
   investigate attaching compiler/GNATprove evidence without making it diagram
   semantics.

A parser such as AdaCore Libadalang is a candidate frontend. Parser selection is
an implementation decision and must be justified by evidence; Drakon-ada should
not grow a handwritten Ada parser merely to reach the first milestone.

## Historical DRAKON-to-Ada checkpoint

The repository began in the opposite direction: authoritative DRAKON diagrams
were used to generate Ada/SPARK. That work remains valuable as qualified research
into DRAKON structured control flow and Ada/SPARK representation.

Checkpoint `6f179ac` demonstrated:

```text
DRAKON movement diagram -> generated Ada/SPARK -> compilation -> GNATprove -> runtime tests
```

Later work qualified minimal structured branching and loops. These checkpoints are
preserved for provenance and regression evidence, but **extending the generator is
no longer the active product direction**. Existing generator material should not
be deleted merely to make the pivot look clean; retire or archive it only when its
remaining evidence value is understood.

## Current repository map

- `generator/ada.tcl` — historical shared Ada emitter and generation profiles
- `integration/drakon-editor/` — editor integration and repository browsing work
- `examples/` — historical qualified DRAKON-to-Ada examples and probes
- `tests/` — existing qualification/regression tests
- `docs/control-flow.md` — historical structured-control-flow qualification
- `docs/repository-browser.md` — current diagram browser behavior
- `docs/observation-architecture.md` — active source-to-observation boundary
- `upstream.lock` — exact official DRAKON Editor commit used by existing integration
- `toolchain.lock` — qualified toolchain references for historical verification

## Existing historical verification

The previous generator checkpoint remains reproducible with the qualified
prerequisites:

```sh
python3 tools/verify.py
python3 tools/check_clean.py
```

Those commands verify the historical generation path. They are **not** yet a
verification gate for the new Ada/SPARK-to-DRAKON observation path.

## License and provenance

New Drakon-ada work is licensed under [MIT](LICENSE). See [NOTICE](NOTICE) and
[the fixed-commit licensing audit](docs/licensing.md) for upstream adaptations,
third-party exceptions, and the source-only distribution boundary. The editor,
its bundled components, and external toolchain are not relicensed by our MIT file.
