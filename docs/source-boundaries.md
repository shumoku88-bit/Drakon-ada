# Sources of truth: movement slice

| Concern | Authority | Derived output |
|---|---|---|
| Control flow and assignments | `examples/movement/movement.drn`, `items` / diagram geometry | Procedure body |
| Semantic contract, parameter and type domains | Same `.drn`, `diagram_info` row named `ada` | Package specification |
| Ada syntax and SPARK profile restrictions | `generator/ada.tcl` | `.ads` / `.adb` formatting and aspects |
| Tool selection | `upstream.lock`, `toolchain.lock`, reproduction instructions | Local fetched dependencies |

`movement.drn` is an editable SQLite DRAKON document (format 22), not a generated
image. It contains two action icons: `Source := -Amount;` and
`Destination := Amount;`, linked by the diagram's vertical flow. There is no
movement implementation template in the generator.

The custom `ada` property is a **data-only Tcl dictionary**, never evaluated as a
script. Inspect it with:

```sh
sqlite3 examples/movement/movement.drn \
  "select value from diagram_info where name = 'ada';"
```

Its schema-1 fields are `schema`, `profile`, `package`, `declarations`, `parameters`
and `post`. Movement keeps schema 1 unchanged. The control-flow step adds an
opt-in [schema 2](control-flow.md) for explicit loop annotations and termination.
The movement example has explicit declarations:

```text
{integer Quantity -2000000 2000000}
{subtype Positive_Amount Quantity 1 1000000}
```

and explicit parameters and contract:

```text
{Amount in Positive_Amount}
{Source out Quantity}
{Destination out Quantity}

Source = -Amount and then Destination = Amount and then Source + Destination = 0
```

The profile only controls generation restrictions / `SPARK_Mode`; it does not
infer this contract. No `Pre` is needed for this example: the admissible input
domain is the explicit `Positive_Amount` subtype. Negative/zero/out-of-domain
amounts are not silently clamped or accepted. A future input reader would need
its own validation; there is no input reader in this slice.

Quantity's declared range represents either signed effect and their intermediate
sum even for two values of magnitude 1,000,000. This avoids relying on an
implementation's unusually wide base integer type for the intended arithmetic.
GNATprove currently leaves no separate run-time VC after range reasoning; the
proof report is recorded accurately, not reinterpreted as additional checks.

Changing the diagram to `Source := Amount;` leaves the explicit negative-source
contract unchanged. The generated program still compiles, but its postcondition
fails proof (Amount = 1 is a reported counterexample). This is the negative proof
control in `tools/verify.py`. Conversely, changing only metadata changes only the
specification. Generation tests check both directions.

## Intentionally limited surface

Only one diagram/procedure/package per document is currently supported. Type
metadata admits explicit integer ranges and constrained subtypes. Actions admit
one assignment per line; expressions are conservatively restricted. This is not
a general Ada parser, an untrusted-input sandbox, or a complete SPARK legality
checker. GNAT and GNATprove remain mandatory.

No proof-bypassing pragmas, hidden control flow, function-call escape hatches,
or goto are accepted in this slice. Raw declarations/headers are not injected.
No generated contract is adopted without an explicit source change. There is no
AI inference in generation. Do not claim that future general Ada expressions
can be safely validated by the current small whitelist.

The control-flow step explicitly adds anchored loop invariants/variants and
Always_Terminates in schema 2; they are not inferred from diagrams. Arbitrary
Pre/Global/Depends metadata, richer types and parameter-icon integration remain
future schema work, not implicit features.
A custom property-editing GUI has not been added; SQLite editing is currently
required for metadata. Editor save/reopen preservation must be tested before
claiming an end-to-end GUI authoring workflow.

`build/generated/` is disposable. `tests/golden/` contains byte-for-byte snapshots
copied from generation and is only a regression oracle, never an implementation
input. Update snapshots by regeneration and review the source change; never fix
a defect by editing generated Ada. No LOAM implementation or operational data
has been imported.
