# DRAKON Editor Repository Browser

## Overview

The **Repository Browser** provides an in-editor navigation pane in DRAKON Editor, allowing developers to inspect and switch between multiple `.drn` diagrams across the `Drakon-ada` repository without opening file dialogs.

The left pane of DRAKON Editor is organized into two tabs:
- **Repository**: Cross-repository hierarchy showing canonical examples and working diagrams.
- **Current file**: The original single-file diagram tree (`mtree`), preserving complete backward compatibility with upstream editing operations.

---

## Architecture & Pinned Upstream Isolation

To preserve reproducibility and respect the repository setup invariant:

1. **Clean Upstream**:
   `.upstream/drakon_editor` is locked to commit `a22609c4e5b1766c953cbfa2fa2234e69e38f9bd` and is **never modified**.
2. **Deterministic Disposable Runtime**:
   `tools/run_editor.py` completely recreates an isolated runtime copy under `build/editor-runtime/` on each launch, leaving zero stale files.
3. **Extension & Plugin Injection**:
   - `generator/ada.tcl` is placed in `build/editor-runtime/generators/ada.tcl`.
   - `integration/drakon-editor/repository_browser.tcl` is placed in `build/editor-runtime/extensions/repository_browser.tcl`.
   - A minimal 2-line hook is added after `mw::create_ui` in the runtime copy of `drakon_editor.tcl` to unpack the left pane into a `ttk::notebook` with `Repository` and `Current file` tabs.
4. **Working Copy & Canonical Promotion**:
   - `quantityAt [working]` resolves to the human-approved `build/quantity-at-two/noop-clean/quantity_at_two.drn`.
   - The scanner checks canonical diagrams first: when a probe is promoted to `examples/`, it seamlessly overrides the working candidate without temporary-path breakage.
5. **No `.drn` Synthesis**:
   Diagrams are never copied into a monolithic workspace file. Navigation directly opens each original `.drn` SQLite file.

---

## Launching the Editor

Launch the editor using the provided runtime wrapper:

```bash
python3 tools/run_editor.py
```

To open a specific `.drn` on startup:

```bash
python3 tools/run_editor.py examples/loam-active-prefix-probe/active_prefix_fold.drn
```

To rebuild the runtime environment from scratch:

```bash
python3 tools/run_editor.py --clean
```

---

## Repository Tree Layout

The tree displays:
- **LOAM probes**:
  - `balance → retained sequence` (`Admit_Three_Changes`)
  - `bounded changes → active prefix` (`Fold_Four`)
  - `active prefix → coordinate/quantity pairing` (`Fold_Active_Prefix`)
  - `quantityAt [working]` (`Quantity_At_Two`)
- **Control flow**:
  - `branch` (`Absolute_Value`)
  - `countdown` (`Count_Down`)
- **Movement**:
  - `movement` (`Balanced_Movement`)

Clicking any diagram node immediately opens that `.drn` in the editor and selects the corresponding diagram on the canvas. The Repository tab remains active and ready for subsequent jumps.

---

## Safety & Non-Mutation

- The Repository Browser accesses `.drn` files via read-only SQLite connections during discovery.
- File switching inside the editor cleanly closes the previous database (`mod::close`) and opens the target file without saving or mutating file bytes.
- Automated tests (`tests/test_repository_browser.py`) guarantee byte-for-byte SHA-256 preservation across repeated switching operations.
