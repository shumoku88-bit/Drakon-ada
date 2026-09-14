# Repository / DRAKON map

`tools/repository_map.py` produces a shared review map for a human reviewer and
an AI reviewer. The map is derived evidence, not a second source of truth.

Canonical meaning remains in the checked-in repository sources, especially the
`.drn` SQLite document and its explicit Ada/SPARK metadata.

## Basic use

From the repository root:

```sh
python3 tools/repository_map.py
```

This writes:

- `build/repository-map.md` — human-readable tracked tree plus DRAKON inventory;
- `build/repository-map.json` — machine-readable diagram, item, metadata,
  geometry, tree-node and repository-reference data.

The default map includes checked-in DRAKON sources under `examples/` only. This
keeps the result deterministic and independent of disposable build products.

During an experiment, use:

```sh
python3 tools/repository_map.py --include-build
```

Positive `.drn` working copies under `build/` are then included as `working`
sources. Generated output, evidence directories and known negative-control
working directories are excluded.

## What the map is authoritative enough for

The structured map is intended to remove routine screenshot exchange from most
review work. It exposes enough information for:

- repository ownership and source location;
- diagram names and descriptions;
- action and decision text;
- stored graph-item geometry;
- explicit Ada/SPARK schema/profile/package facts;
- raw diagram metadata in JSON;
- DRAKON tree nodes;
- files in `docs/`, `tests/`, `tools/` and `generator/` that refer to a source;
- distinguishing canonical examples from temporary working diagrams.

The Markdown visual-semantic inventory is sorted by stored `(y, x, item_id)`.
That is a reading aid, not a replacement control-flow semantics. Generated Ada,
upstream graph verification and proof/runtime gates remain the authorities for
normalized behavior.

## When a screenshot is still required

Stored geometry is not rendered pixels. Human GUI review remains necessary when
the question depends on:

- actual Tk font fit;
- rendered label or line clearance;
- visual overlap not represented by simple item bounds;
- subjective reading flow or cognitive load;
- the exact result of DRAKON Editor layout operations such as **Tidy up**.

The intended workflow is therefore: use the map for continuous structural and
semantic review, and request a screenshot only at a genuine visual gate.

## Review pattern

A useful conversation can now start from a map path rather than an image, for
example:

```text
examples/loam-active-prefix-probe/active_prefix_fold.drn
  → Fold_Active_Prefix
  → decision: Index <= Length
```

or:

```text
build/quantity-at-two/noop-clean/quantity_at_two.drn
  → Quantity_At_Two
  → second coordinate decision
```

The reviewer can then inspect the matching source, tests, verifier and metadata
without requiring the user to re-screenshot the whole diagram.
