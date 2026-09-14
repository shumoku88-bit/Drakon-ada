# Reproduce the movement gate

## Prerequisites

Qualified host: **Darwin x86_64**. Other hosts are not yet qualified.

- Git and network access to fetch the locked upstream commit.
- Python 3.11+ (observed: 3.14.6).
- Tcl 8.6 (observed: 8.6.18), Tcl SQLite package (3.53.0), Tcllib
  `json::write` (1.0.5), and `msgcat`. Tk is needed only to open the GUI.
- GNAT 16.1.0, GPRbuild 26.0.0 (Alire package 26.0.1), GNATprove FSF 16.1.0,
  with the bundled provers. Exact platform artifact URLs and SHA-256 values,
  taken from the installed Alire manifests, are in `toolchain.lock`.
  These binaries were already installed locally; downloading/installing the
  compiler toolchain from scratch has not been tested by this project.
- A working platform SDK/linker for GNAT (on macOS, Xcode command-line tools).

Install the toolchain separately (Alire or the locked upstream binary archives).
If using archives, compare each download against its locked SHA-256 before
extracting it. Add the three installations' `bin` directories to PATH:

```sh
export PATH="/path/to/gnat/bin:/path/to/gprbuild/bin:/path/to/gnatprove/bin:$PATH"
gnatmake --version
gprbuild --version
gnatprove --version
tclsh <<'EOF'
puts [info patchlevel]
puts [package require sqlite3]
puts [package require json::write]
EOF
```

`toolchain.lock` documents qualified artifacts; scripts do not install tools or
silently modify global Alire settings. Tool versions are saved in evidence logs.
A missing tool is a failure, never a successful skipped proof. The proof-report
gate is deliberately tied to the qualified movement result; tool upgrades need
review. This is a source-checkout reproduction, not a hermetic OS/toolchain image.

## Full gate

From the repository root:

```sh
python3 tools/verify.py
```

The command **deletes `build/`**, then:

1. Fetches the exact editor commit into ignored `.upstream/drakon_editor` and
   installs the plugin without modifying tracked upstream files.
2. Runs nine generation tests, including deterministic golden output, independent
   diagram/metadata changes, profile behavior and rejected invalid inputs.
3. Regenerates Ada from `examples/movement/movement.drn` into `build/generated/`.
4. Builds the generated package and runtime driver with assertions and overflow
   checks enabled (`-gnata -gnato`), without suppressions.
5. Runs GNATprove for `movement.adb` in `--mode=all`, with unproved checks and
   warnings treated as errors. Requires the expected nonempty result and zero
   justified/unproved checks, not merely exit 0.
6. Executes all 1,000,000 valid values of `Positive_Amount` and checks all three
   equalities. Runtime testing is finite evidence, not the substitute for proof.
7. Mutates the **diagram**, regenerates into a separate directory, confirms it
   compiles, and requires GNATprove to fail on the deliberately wrong postcondition.

Logs are retained in `build/evidence/`. The proof target is the generated Movement
package, not `Ada.Text_IO` or the test driver. There are no imported helper
implementations or external axioms in the proof target.

For generation only (does NOT establish the full success criteria):

```sh
python3 tools/setup.py
tclsh integration/drakon-editor/generate.tcl examples/movement/movement.drn build/generated
python3 -m unittest discover -s tests -v
```

Set `TCLSH` for the Python scripts if Tcl 8.6 has a different executable name.

## Clean checkout check

```sh
python3 tools/check_clean.py
```

This copies only Git-visible project sources to a disposable seed repository,
commits that test snapshot there, makes a clean clone, and runs the complete gate.
It fetches the editor anew, reuses the installed PATH toolchain, and requires a
clean `git status` afterwards. It does **not** commit the working repository or
publish anything. It writes a result marker to `build/evidence/clean-checkout.txt`.

## Inspect/edit sources

Open `examples/movement/movement.drn` with the pinned editor plus installed plugin.
For now, inspect/edit custom metadata through SQLite, not a custom GUI panel.
See [source-boundaries.md](source-boundaries.md). GUI round-trip editing has not
been qualified. Never edit the generated files to make tests pass.

Upstream's full regression suite has independent failures; see
[upstream-audit.md](upstream-audit.md). It is not included as a falsely green gate.
