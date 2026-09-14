# Pinned upstream audit

Repository: https://github.com/stepan-mitkin/drakon_editor

Commit: `a22609c4e5b1766c953cbfa2fa2234e69e38f9bd` (recorded in `upstream.lock`).
All paths below refer to this commit, not a moving branch.

## Registration and integration

- `scripts/generators.tcl:3`: `load_generators` sources `generators/*.tcl`.
- `scripts/generators.tcl:18`: `gen::add_generator language callback` records the callback.
- `generators/go.tcl:1,36`: working registration and callback signature
  `generate {db gdb filename}`. `db` is the source model, read-only by convention;
  `gdb` is the derived writable graph database. Do not change the source model.
- `scripts/file_props.tcl` (`fprops` namespace): language choices come from
  `array names gen::generators`, not a hardcoded language enumeration.
- Both GUI and headless entry points call `load_generators`.

**No tracked upstream patch is necessary.** `tools/setup.py` fetches the pinned
checkout and copies only `generator/ada.tcl` to `generators/ada.tcl`. This registers
Ada and SPARK. GUI registration is source-inspected; interactive GUI editing and
round-trip preservation of our metadata have NOT been tested.

The duplicate-registration guard checks `generator($language)` rather than the
`generators` array. Do not depend on it to detect duplicate language registrations.

## Existing normalization and printer API

In `scripts/generators.tcl`:

1. `graph::verify_all db` constructs/verifies the graph (`scripts/graph.tcl`).
2. `gen::fix_graph_for_diagram gdb callbacks append_semicolon diagram_id`
   (line 779) rewires supported constructs, removes branch icons, glues actions,
   and short-circuits conditions. Our plugin passes `append_semicolon = 0`;
   Ada assignments in action icons already have their explicit semicolons.
3. `gen::generate_functions db gdb callbacks 1` (line 2597) requests nogoto.
4. `gen::generate_function` (line 1935) calls `gen::try_nogoto` (line 2139).
5. `try_nogoto` uses `nogoto::create_db`, `gen::add_to_graph`,
   `nogoto::generate`, `gen::extract_texts`, and `gen::print_node`.
   The existing algorithm is in `generators/nogoto.tcl` (with `.drn` source).
6. The printer consumes nodes such as `seq`, `if`, `loop`, `break` and `sel`.
   Callbacks are registered with `gen::put_callback`. Relevant callbacks include
   `if_start`, `if_end`, `else_start`, `if_block_end`, `while_start`,
   `block_close`, `break`, `signature`, `body`, and `enforce_nogoto`.
7. A generated function is `{diagram_id name signature body}`. The plugin owns
   package/specification formatting, not the graph normalization algorithm.

The optional `if_block_end` callback (line 2328) lets Ada emit `end if;` separately
from `block_close` emitting `end loop;`. No printer patch is needed.
If normalization fails, our fallback callbacks raise an error. No goto fallback.
Movement is straight-line; general if/loop support is **not certified** by that
example. The subsequent [control-flow step](control-flow.md) qualifies two minimal
examples and explicit anchored loop annotations. Foreach, select lowering and
broader icon support remain out of scope. No forward-goto decision has been made or is needed.

## Fail-closed runner

`generate_no_gui` catches `p.do_generate` exceptions, but can still return 1 if
`graph::get_error_list` is empty (`scripts/generators.tcl:97–151`). Package-loading
failure in `drakon_gen.tcl` can also use a bare `exit`. Exit status alone is unsafe
as evidence when using that entry point.

`integration/drakon-editor/generate.tcl` follows the headless bootstrap's explicit
module list, but calls verification and our generator directly inside a strict
catch. It validates upstream HEAD, tracked cleanliness, and installed plugin
contents. No source-text rewriting or upstream monkey patch is used. API changes
require reviewing this bootstrap when updating the lock.

## Upstream regression mechanisms and actual results

`README.md:18–30` requires:

- Run `unittest/unittest.tcl` from `unittest/`. Expected negative-test diagnostics
  are allowed, but the final line must be `success`.
- Add new `.drn` sources to `unittest/regenerate.sh`.
- For generator changes, update and run `unittest/regenerate_examples.sh`.

The regeneration scripts invoke the headless generator repeatedly; they are not
standalone golden-diff assertions and lack `set -e`. Check statuses, diagnostics,
and output diffs separately. Run upstream regeneration in a disposable checkout.

Observed on Tcl 8.6.18 / Tcl SQLite 3.53.0, in a separate unmodified checkout:

- Full unit suite: **FAIL**, exit 1 in `find_all_test`:
  `no such column: "different" - should this be a string literal in single-quotes?`
  The test uses `update diagrams set name = "different" ...`; modern SQLite
  double-quoted-string compatibility differs. No compatibility patch applied.
- Focused `tclsh unittest.tcl nogoto_test`: **PASS**, final `success`.
- `bash -e regenerate_examples.sh`: **FAIL**, exit 1 at missing
  `examples/Erlang/erldemo.drn` (absent at this pinned path). Earlier output
  also contains a swallowed exception:
  `wrong # args: should be "gen::p.save_declare_kernel gdb diagram_id lines loop"`.

Thus upstream's full regression suite is **not reported green**. Our nine
baseline movement-generation tests and full movement gate are separate evidence.
The subsequent control-flow extension is documented separately in [control-flow.md](control-flow.md).

## License boundaries

- `readme.html:394–395`: DRAKON Editor is PUBLIC DOMAIN **except** third-party
  components, explicitly naming pdf4tcl and Liberation fonts.
- `pdf4tcl07/licence.terms`: permissive copyright license; existing notices must
  be retained and the license included verbatim in distributions.
- `fonts/License.txt`: this bundled Liberation font version uses GPL v2 with
  the listed font-embedding and other exceptions. Do not replace this fact with
  the license of a newer font release.
- Tcl/Tk, Tcllib, SQLite, GNAT, GNATprove and provers remain separately licensed
  external tools. Upstream's Public Domain statement does not cover them.

This independent repository does not vendor the editor, fonts or pdf4tcl;
`.upstream/` is ignored. The small example diagram was constructed locally using
upstream's documented SQLite schema, not copied from a household dataset.
Public distribution of a bundled editor would require another component audit.
The owner selected **MIT for new Drakon-ada work** after the final fixed-commit
review in [licensing.md](licensing.md). That review also records macOS launcher
copyright headers that qualify blanket Public Domain claims. Upstream's statement
does not license this new code or erase those headers; see root `LICENSE` and `NOTICE`.
