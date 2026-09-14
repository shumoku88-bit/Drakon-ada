# Drakon-ada

- Independent plugin for the commit in `upstream.lock`; no upstream patches without evidence.
- Scope is `examples/movement/` only. Do not start a LOAM migration or import private data.
- Control flow/assignments: DRAKON `.drn`; semantic contracts: explicit `ada` property;
  Ada/SPARK syntax/restrictions: shared generator/profile. Never infer canonical contracts.
- Generated Ada is derived. Fix the sources and regenerate; never hand-edit generated code.
- Reuse upstream nogoto normalization. No goto fallback, assumptions, suppressions or hidden proof exclusions.
- `python3 tools/verify.py` is the complete gate; it deletes `build/`.
  `python3 tools/check_clean.py` tests a disposable clean Git clone.
- Missing proof tools or failing upstream regressions are not a successful skipped check.
- Report target VC coverage, actual proof totals and limitations, not just process exit status.
- Tool output rules: use `rtk git`, `rtk test`, and `rtk err` where applicable;
  keep exact raw compiler/proof evidence and failing statuses when needed.
- Call AI collaborators `pit` in project documentation, unless a specific model matters.
- New project work is MIT; retain LICENSE, NOTICE and upstream provenance. See docs/licensing.md.
- Do not vendor upstream/toolchain assets or change upstream.lock without repeating the license audit.
- Public remote creation/push requires explicit authorization; a local checkpoint is not a publication request.
