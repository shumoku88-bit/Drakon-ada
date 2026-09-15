# End-to-end observation command (Phase O4)

Phase O4 connects the already-qualified observation pipeline behind one command.
It does not add a new control-flow model or reinterpret Ada source.

Authority remains:

```text
Ada/SPARK source
  -> Libadalang normalized observation
  -> renderer-independent DRAKON projection
  -> derived DRAKON Editor .drn
```

## Command

With a qualified Libadalang environment available:

```sh
python tools/observe_to_drakon.py examples/source-observation/observation_fixture.adb
```

The default output follows the normalized source identity under `build/drakon/`:

```text
build/drakon/examples/source-observation/observation_fixture.drn
```

Use `--output` / `-o` to choose another destination. `--source-root` and
`--charset` are forwarded unchanged to the qualified source observer.

## Boundary

`tools/observe_to_drakon.py` imports and calls exactly these existing stages:

1. `observe_ada.observe`
2. `project_drakon.project_observation`
3. `write_drakon.write_projection`

There is no subprocess pipeline, no temporary observation JSON, no temporary
projection JSON, and no new semantic transformation in O4.

The final `.drn` is written through a temporary file in the destination
directory and atomically replaces the destination only after the writer
returns successfully. A failed observation, projection, or write therefore
does not destroy an older generated document.

The default output path is derived only from the normalized observation's
stable relative source identity. Absolute paths and parent traversal are
refused.

## Qualification

The lightweight O4 tests deliberately do not rebuild Libadalang. They verify
only orchestration responsibilities:

- observer -> projector -> writer ordering,
- argument forwarding,
- stable default output naming,
- no intermediate JSON artifacts,
- atomic preservation of an existing `.drn` on failure,
- fail-closed output-path handling.

The frontend itself remains covered by the separate Source Observer
Qualification. Projection, SQLite rendering, pinned-editor verification, and
semantic round-trip remain covered by the DRAKON Projection workflow.
