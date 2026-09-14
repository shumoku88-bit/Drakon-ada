# Drakon-ada

An independent Ada/SPARK generator plugin for the official
[stepan-mitkin/drakon_editor](https://github.com/stepan-mitkin/drakon_editor).

## Project boundary

- **DRAKON diagrams and explicit contract metadata are the sources of truth.**
- Generated Ada/SPARK is derived output: regenerate it rather than hand-edit it.
- Ada and SPARK share **one Ada emitter with generation profiles**, not two
  independent semantic engines.
- The **SPARK profile does not guarantee proof**. It provides a restricted
  generation path and a GNATprove verification workflow; actual checks must pass.
- **LOAM is a future practical example, not a dependency or prerequisite** of
  this generator. No LOAM migration has begun.

First checkpoint (`6f179ac`): **one DRAKON movement diagram → generated Ada/SPARK
→ compilation → GNATprove → runtime tests**. The next step qualifies minimal
[structured if/else and loop examples](docs/control-flow.md), without altering
that checkpoint.

For every `Amount` in `1 .. 1_000_000`, the example specifies:

- `Source = -Amount`
- `Destination = Amount`
- `Source + Destination = 0`
- Safe bounded arithmetic and initialized outputs.

Control flow belongs to the DRAKON diagram; the semantic contract belongs to
explicit metadata; Ada/SPARK output rules belong to the shared generator/profile.
Contracts are never inferred. Generated Ada is never edited by hand.

## Run

With the [qualified prerequisites](docs/reproduction.md) installed:

```sh
python3 tools/verify.py
python3 tools/check_clean.py
```

`verify.py` deletes `build/`, regenerates everything, and refuses missing tools,
unproved checks, justified checks or an unexpectedly empty proof. A deliberately
incorrect diagram must compile but fail its unchanged contract as a negative
control. No goto fallback, assumptions or suppressions are used.

## Map

- `upstream.lock` — exact official editor commit
- `generator/ada.tcl` — shared Ada emitter with Ada/SPARK profiles
- `integration/drakon-editor/generate.tcl` — strict headless runner, no upstream patch
- `examples/movement/movement.drn` — authoritative diagram and explicit metadata
- `tests/golden/` — generated regression snapshots, not implementation sources
- `toolchain.lock` — qualified Darwin x86_64 binary artifact references
- [Upstream audit](docs/upstream-audit.md) — registration, APIs, tests and licenses
- [Source boundaries](docs/source-boundaries.md) — current metadata schema and limits
- [Reproduction](docs/reproduction.md) — commands and evidence interpretation
- [Verification result](docs/verification.md) — observed results and outstanding limits

## Current limitations

- Qualified examples are straight-line movement, two-way absolute-value branching,
  and a pre-test countdown loop; this is not a complete Ada/SPARK backend.
- **GUI editing and metadata save/reopen round-trips are unverified.** Metadata
  currently requires SQLite editing; no custom property panel is provided.
- Minimal structured `if` / `loop` generation and explicitly anchored invariant/
  variant metadata are verified by the control-flow examples. **Arbitrary nesting,
  multiple exits, post-test loops and foreach remain unverified.** There is no
  goto fallback.
- Full upstream regression suites have known failures; they are not claimed green.
- Clean-checkout reproduction is qualified on Darwin x86_64 with preinstalled
  tools, not a clean OS image. Other platforms and hosted CI are not qualified.
- Proof covers the generated example targets, not correctness of the generator
  in general or a guarantee for arbitrary diagrams.

## License and provenance

New Drakon-ada work is licensed under [MIT](LICENSE). See [NOTICE](NOTICE) and
[the fixed-commit licensing audit](docs/licensing.md) for upstream adaptations,
third-party exceptions and the source-only distribution boundary. The editor,
its bundled components and external toolchain are not relicensed by our MIT file.

## Publication status

Independent local Git repository with separate movement and basic structured
control-flow checkpoints. No public push has been made.
