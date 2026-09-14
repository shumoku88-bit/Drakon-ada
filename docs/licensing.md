# Licensing audit and publication boundary

## Decision

Drakon-ada's new code, documentation, synthetic movement source and checked-in
example snapshots are offered under the root [MIT license](../LICENSE).
The copyright holder uses the repository owner's configured Git name,
Mokutaro Akatsuka (2026). This does **not** relicense DRAKON Editor, its authors'
work, bundled third-party components, or external compiler/prover tools.

No incompatible notice was found in the Tcl integration material used here.
MIT is appropriate for this independent source-only plugin checkpoint on the
examined evidence. This is a bounded engineering audit, not a legal opinion or
an assertion that every upstream asset is unconditionally Public Domain.

## Exact evidence scope

- Repository: https://github.com/stepan-mitkin/drakon_editor
- Commit: **`a22609c4e5b1766c953cbfa2fa2234e69e38f9bd`**, as in `upstream.lock`.
- All upstream references below are relative to this commit. For example:
  [pinned license statement](https://github.com/stepan-mitkin/drakon_editor/blob/a22609c4e5b1766c953cbfa2fa2234e69e38f9bd/readme.html#L394-L395).
- Git tree inspection, not the moving branch or a GitHub license badge, determines
  which files exist. The locally installed untracked `generators/ada.tcl` is not
  evidence of the upstream license.

### LICENSE / COPYING inventory

There is **no root LICENSE, COPYING, or equivalent standalone license file** at
this commit. The recursively named license files are:

| Upstream path | Observed content |
|---|---|
| `pdf4tcl07/licence.terms` | Custom permissive terms with notice-preservation conditions |
| `fonts/COPYING` | GNU General Public License, version 2, June 1991 |
| `fonts/License.txt` | Liberation font agreement, GPL v2 with stated exceptions |

The actual project-wide statement is in `readme.html:394–395`:

> DRAKON Editor is PUBLIC DOMAIN except some third-party components (pdf4tcl, Liberation fonts).

`readme_mac.html:349–350` repeats it. `scripts/about.tcl:25` independently says
that the software is Public Domain except pdf4tcl and Liberation fonts, which
have their own licenses. `msgs/ru.msg:100` includes the same statement.
These are plain Public Domain statements, **not** an MIT license or an explicit
CC0 instrument. We do not substitute an SPDX license or invent a fallback grant.

## Per-source-file copyright/license headers

[upstream-source-notices.tsv](upstream-source-notices.tsv) records one row per
source file (292 files) in the selected textual programming-language extensions,
with line-numbered notice keyword matches from the **entire** source. Regenerate:

```sh
python3 tools/setup.py
python3 tools/license_inventory.py > docs/upstream-source-notices.tsv
```

The script reads fixed-commit Git objects. `NONE` means no keyword match, not an
independent license grant. It is a reproducible inventory, not a license scanner
capable of resolving legal ambiguity. Binary `.drn` documents, executables,
images, font binaries and document formats are not classified by this scan.
The license documents and significant headers were separately read.

| Source(s) | Header / notice finding and treatment |
|---|---|
| `drakon_gen.tcl`, `drakon_editor.tcl` | No copyright/license header found; rely on the project-level statement for these Tcl entry points |
| `scripts/generators.tcl`, `scripts/graph.tcl`, `scripts/model.tcl`, `scripts/utils.tcl`, `scripts/file_props.tcl` | No separate copyright/license header found; project-level statement is the evidence, not mere absence of a header |
| `generators/go.tcl`, `generators/nogoto.tcl` and other core Tcl generator files | No separate copyright/license header found; some have generated-code banners, which are not license grants |
| Other source files | Individually listed in the TSV; no additional matching notice beyond the rows summarized here |
| `scripts/about.tcl` and `msgs/ru.msg` | Explicit Public Domain statement with named third-party exceptions |
| `pdf4tcl07/pdf4tcl.tcl:4–10` | Frank Richter and Jens Poenisch (2004), Peter Spjuth (2006–2010), Yaroslav Schekin (2009); explicitly refers to `licence.terms` for redistribution and warranty terms (original name bytes retained upstream) |
| `pdf4tcl07/glyph2uni.tcl:1667–1669` | `copyright` glyph names, not copyright/license headers |
| `examples/Erlang/basic/basic.erl:8–9` | Copyright 2015 Stepan Mitkin; explicit Public Domain statement |
| `examples/Erlang/fsm/code_door.erl:13–14`, `lexer.erl:12–13` | Copyright 2015 Stepan Mitkin; explicit Public Domain statement |
| `examples/automaton/C#/Properties/AssemblyInfo.cs:13` | `AssemblyCopyright("Copyright ©  2018")`; not a distinct license grant; not used here |
| `DRAKONEditor/DRAKONEditorAppDelegate.h:6`, `DRAKONEditorAppDelegate.m:6`, `main.m:6` | `Copyright 2011 __MyCompanyName__. All rights reserved.`; apparent template text, but **not assumed void or overridden**; these launcher files are neither copied nor redistributed here |

The macOS launcher headers are a real qualification to any blanket statement
about upstream licensing. Clarify them with upstream before bundling that
launcher. They do not supply code to this plugin or its headless runner.

## Bundled third-party components

### pdf4tcl 0.7

`pdf4tcl07/pdf4tcl.tcl` identifies package version 0.7 and points to
`pdf4tcl07/licence.terms`. Those terms permit use, copying, modification,
distribution and licensing for any purpose, **provided existing copyright notices
are retained and the terms included verbatim in distributions**. Modified work
may carry different terms if those are clearly indicated as specified there.
The terms include warranty/liability disclaimers and government-use provisions.
Do not call this component Public Domain or simply replace its terms with MIT.
Documentation also credits Peter Spjuth (2007) and Yaroslav Schekin (2009).

### Liberation fonts

`fonts/README:49–57`, `fonts/COPYING`, and `fonts/License.txt` identify GPL v2 with
specific exceptions. The font agreement includes the unaltered-font embedding
exception, a physical-product/source/reinstallation condition, and restrictions
on Red Hat/Liberation trademarks and modified font names. It credits Red Hat,
Inc. (2007). Do **not** substitute the SIL OFL of a different font release.
Redistributing this font requires retaining and complying with its actual terms,
not treating it as MIT or assuming that attribution alone is sufficient.

### Not part of this release

Drakon-ada checks in neither of those components, nor upstream images,
executables, launcher sources or example binaries. `.upstream/` is ignored;
`tools/setup.py` fetches a separate upstream checkout locally, retaining its
license files intact. A source checkout that downloads a dependency is not a
license grant over that dependency.

Tcl/Tk, Tcllib (including packages required by upstream), SQLite, GNAT/GPRbuild,
GNATprove and bundled provers are external tools with their own terms. They are
not redistributed in this source-only checkpoint. A future all-in-one editor,
container or binary release needs a new distribution-specific audit; this report
does not clear all upstream binaries/assets or toolchain components for bundling.

## What was copied or adapted into Drakon-ada?

**Independent repository does not mean zero upstream-derived material.**

| Drakon-ada path | Provenance |
|---|---|
| `integration/drakon-editor/generate.tcl` | Adapted headless bootstrap/module ordering and verification/setup protocol from upstream `drakon_gen.tcl` and `scripts/generators.tcl`. Explicitly replaces the CLI error-handling path; not a verbatim copy of the whole entry point. Credit retained in the file and `NOTICE`. |
| `generator/ada.tcl` | Newly written Ada/profile/metadata code. Registration, callback wiring, generation sequence and small indentation/output idioms follow upstream `generators/go.tcl` and `scripts/generators.tcl`. The graph/tree algorithm is **called from the fetched upstream**, not copied into this repository. Conservatively credit those reference patterns as adaptations. |
| `examples/movement/movement.drn` | New synthetic diagram/assignments/metadata. Its SQLite format/table layout was constructed from the inspected upstream format and example schema, not invented independently. No upstream example algorithm, artwork, household data or LOAM code was copied. |
| `examples/control-flow/branch/branch.drn`, `countdown/countdown.drn` | New synthetic contracts and algorithms, constructed using the same SQLite schema. Branch/return-arrow layout patterns were adapted from the pinned `docs/AutoHotkey/Diagrams from Documentation/6 (if).drn` and `10 (Check-Do loop).drn`; no AHK implementation or binary asset is bundled. These examples have no separate license notice in the inspected source text and are covered by the project-level Public Domain statement. |
| `tests/golden/movement.ads`, `movement.adb` | Derived from that synthetic source and this emitter using upstream normalization. No upstream runtime implementation is pasted into the Ada output. |
| `docs/upstream-source-notices.tsv`, licensing/audit documentation | Factual inventory and short attributed notice/API excerpts, not bundled upstream implementations. |
| Python setup/verification/tests, movement runtime driver and GPR file | New project code; invokes external tools rather than vendoring them. |

No pdf4tcl, font or macOS launcher implementation was copied into these files.
No complete upstream implementation file is vendored. The adaptations above
rely on the pinned project's Public Domain statement for the relevant Tcl core;
MIT applies to our new contributions, not a claim of authorship over that core.

## Attribution and distribution requirements

1. Ship root `LICENSE` with copies/substantial portions of the new MIT work, as
   required by MIT. Keep `NOTICE` with source distributions as project policy.
2. The examined Public Domain statement for the Tcl core imposes no explicit
   attribution condition. Nevertheless, `NOTICE`, source comments and this report
   identify upstream, the fixed commit, the relevant adapted paths, and authors
   listed in `readme.html:398–399`: Stepan Mitkin, Alexander Ilyin, Maas-Maarten
   Zeeman, Vasil Dyadov and Vasili Bachiashvili. This is provenance, not a claim
   that upstream endorsed Drakon-ada or that MIT changes the original status.
3. No pdf4tcl/font license bundle is needed **for this source-only plugin's
   contents**, since their implementations/assets are absent. If bundling them
   later, include their original notices/licenses and meet their substantive
   requirements; this MIT file is not a replacement.
4. Do not force-add `.upstream/` or `build/` to a release. Recheck the staged file
   list before publication. Resolve the launcher header ambiguity before any
   launcher redistribution, and repeat this audit when changing `upstream.lock`.

Generated outputs in general do not acquire a universal license just because
this generator is MIT. Their source inputs and any incorporated material matter;
only this repository's own synthetic example/snapshots are covered here.
