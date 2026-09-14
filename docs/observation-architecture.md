# Ada/SPARK observation architecture

## Purpose

Drakon-ada now treats DRAKON as an **observation surface** over Ada/SPARK source.
The implementation source remains canonical. The observation exists to make
control-flow shape inspectable by humans and AI while retaining a precise route
back to the code that produced every visible node and edge.

This is intentionally not a round-trip editor architecture.

```text
canonical Ada/SPARK source
          |
          v
  source/semantic frontend
          |
          v
 normalized control-flow observation
        /           \
       v             v
machine-readable    DRAKON
   sidecar         projection
        \           /
         v         v
        human + AI review
               |
               v
       edit canonical source
```

## Sources of truth

There is one source of program truth:

1. Ada/SPARK source files.

Derived evidence may include:

- normalized control-flow observations;
- DRAKON files/images;
- source-span indexes;
- compiler/test/GNATprove evidence overlays.

Derived artifacts may be cached or committed for regression purposes, but they do
not acquire authority merely by being stored in the repository.

## Observation contract

A trustworthy observation frontier must satisfy these properties.

### 1. Traceability

Every semantic control-flow node carries enough source identity to answer:

- which source file produced it;
- which compilation unit/subprogram it belongs to;
- the exact source span that produced it;
- which normalized node kind was assigned to it.

A visual DRAKON node must retain the normalized node identity so a reviewer can
move from picture to machine-readable graph to source without guesswork.

### 2. No silent loss

An unsupported Ada construct is not permission to draw a simpler program.

The frontend must either:

- represent the construct faithfully;
- emit an explicit `unsupported` observation tied to its source span; or
- refuse the projection.

Silent omission is a correctness failure for this tool even when the original Ada
program itself is valid.

### 3. Renderer independence

The normalized model must not be a thin encoding of DRAKON SQLite/layout details.
It should describe observed control flow first. A renderer then chooses how to
project that graph into DRAKON.

This separation keeps later SVG, text, JSON, or alternative visual renderers from
requiring a second source parser or semantic engine.

### 4. Determinism

For the same source revision, frontend version, and observation options, the
normalized graph must be stable. Layout determinism is desirable, but semantic
node/edge determinism is required first.

### 5. Evidence separation

Source structure, compiler legality, contracts, proof results, and runtime test
results are different kinds of evidence.

The control-flow observer may attach references to those facts later, but it must
not infer one from another. In particular:

- a DRAKON shape is not a proof;
- a GNATprove success is not source parsing;
- a contract is not inferred from a branch label;
- a pretty diagram is not evidence that unsupported source was handled.

## Minimal normalized model

The first implementation should stay deliberately small. The exact representation
is not fixed by this document, but the semantic surface should resemble:

```text
SubprogramObservation
  source_file
  unit_identity
  subprogram_identity
  entry_node
  nodes[]
  edges[]

Node
  id
  kind
  source_span
  label/reference

Edge
  from
  to
  role
```

Initial node kinds need only cover the first qualified slice, for example:

- entry / exit;
- straight-line action;
- decision;
- loop entrance/back edge;
- return;
- explicit unsupported.

Initial edge roles can remain equally small:

- next;
- true / false;
- loop body / loop exit / back;
- return.

Do not add a distinction until a real Ada construct or review need requires it.

## Frontend direction

Drakon-ada should not implement a general Ada parser by hand.

AdaCore Libadalang is the leading candidate for the first source/semantic frontend
because it is designed for programmatic Ada analysis and exposes source structure
through APIs suitable for an external observer. This is a candidate, not yet a
qualified dependency.

Before adoption, a small probe should establish at least:

- installation/reproduction on the current development platform;
- exact source span recovery;
- traversal of one procedure body;
- reliable identification of sequential statements, `if`/`elsif`/`else`, loops,
  and returns for the first target slice;
- behavior on SPARK aspects/contracts present around the body;
- licensing and distribution implications;
- behavior on parse/semantic errors.

If Libadalang cannot support a required observation accurately, record the gap
before adding workarounds.

## DRAKON projection

DRAKON is downstream of the normalized graph.

The renderer may choose visual layout, branch orientation, labels, icons, and
navigation metadata, but must not rewrite observed program structure to obtain a
prettier diagram.

The existing official-editor integration and repository browser are potentially
useful rendering/navigation assets. They are not part of the canonical source
frontier.

A future generated DRAKON artifact should identify at least:

- source revision or source digest;
- frontend/observer version;
- observed subprogram identity;
- normalized node IDs represented by each visual item.

## Machine-readable sidecar

The visual diagram is deliberately paired with a machine-readable observation.
This matters for AI-assisted review as well as regression testing.

The sidecar should allow a reviewer or tool to ask precise questions such as:

- Which source span corresponds to this decision node?
- How many exits does this subprogram have?
- Which path contains the most sequential actions?
- Are two visual decisions backed by the same source condition or by distinct
  source constructs?
- Did a source edit alter control-flow semantics or only layout/text?

JSON is an acceptable first transport if it remains a serialization of the
normalized model rather than the model itself.

## Historical generator boundary

The existing DRAKON-to-Ada generator and its qualified examples are historical
research evidence. They taught the project about DRAKON structured control flow,
Ada/SPARK generation constraints, GNATprove qualification, and editor integration.

They are not the active canonical direction after this pivot.

The preservation rule is:

- keep qualified checkpoints reproducible while they still provide evidence;
- do not expand generator capability merely because a new source construct is
  needed by the observer;
- do not force the new observer through the old generator representation;
- archive/retire historical machinery only after an explicit audit shows what
  evidence would be lost.

## First practical target: hra-n

The first intended real design-observation target is `hra-n`, an external
Ada/SPARK project under active development.

The first success criterion is not "a picture was generated". It is:

1. select one bounded hra-n subprogram/path;
2. observe it from canonical Ada/SPARK source;
3. inspect both DRAKON and the machine-readable graph;
4. identify a concrete structural design question or simplification candidate;
5. trace that observation back to exact source;
6. change the source only if normal engineering evidence supports the change;
7. regenerate and observe the new shape.

No hra-n source or private data should be copied into Drakon-ada merely to perform
this experiment.

## Immediate implementation sequence

### Phase O0: pivot boundary

- redefine source of truth and contribution rules;
- preserve old qualification as historical evidence;
- stop extending DRAKON-to-Ada as the active product direction.

### Phase O1: frontend probe

- add the smallest Ada source fixture owned by Drakon-ada;
- inspect it with the candidate frontend;
- emit exact source spans and a simple textual/JSON observation;
- cover straight-line, decision, and loop constructs only.

### Phase O2: normalized control flow

- introduce the minimal renderer-independent node/edge model;
- test determinism and no-silent-loss behavior;
- add negative fixtures for unsupported syntax.

### Phase O3: DRAKON renderer

- project the qualified normalized model into DRAKON;
- embed node/source identity metadata;
- reuse editor/browser integration where it reduces work without creating
  semantic coupling.

### Phase O4: hra-n observation

- run the observer against a bounded external hra-n slice;
- use the diagram and sidecar during an actual design review;
- record what the visual observation revealed and whether the source was improved.

Proof/evidence overlays come later. First make the source-to-shape observation
trustworthy.
