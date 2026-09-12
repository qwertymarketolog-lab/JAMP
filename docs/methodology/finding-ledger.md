Living document. Issue #41 is the discussion surface.
This file is the canonical list of methodology findings.
New findings appended via new commit; existing entries
are not edited in place. Status transitions are recorded
as new entries, not as edits.

The following methodology findings are now recorded as an Issue-level ledger mirror. They remain OPEN until promoted to the repository methodology artifact.

| Finding ID | Mode | Instance | Detected by | Consequence | Generalization | Status |
|---|---|---|---|---|---|---|
| M-001 | frozen-reference under-specification | seeds `[0,1,2,42,99]` existed in historical `track_a/results/README.md`, but were not declared with provenance in the Closure Scan preregistration | cross-artifact audit | a supposedly frozen scan can inherit an unstated historical parameter | every frozen reference must have a value + source + scope, or explicit OPEN marker | OPEN |
| M-002 | cross-artifact parameter inconsistency | historical Track-A design has `max_objects=120`; current scan/P1 record has `150`; P2 actual cap is uncertain | parameter provenance audit | P1/P2 comparability could be misstated | one canonical parameter record must trace every execution parameter to a source | OPEN |
| M-003 | search-method substitution | `search_commits` was initially treated as evidence analogous to `git log -S` | C.1 method review | commit-message search produced a false-positive route for component archaeology | metadata search is not content-history search; exclude it as component-presence evidence | ADDRESSED |
| M-004 | current-tree → historical inference | `JUMP` was initially inferred from a test-name occurrence at the anchor | direct content verification | a lexical occurrence was mistaken for a historical/component claim | direct read establishes only anchor presence; first-commit claims require file-history or bounded tree archaeology | ADDRESSED |
| M-005 | unresolved forward reference | `src/jamp/domain/__init__.py` imports `.causal`, including `VectorClock`, while `src/jamp/domain/` at `49a5c86` contains only `__init__.py` | direct directory + file read | anchor tree contains an unconditional import whose target is absent; implementation provenance is unresolved | imports must resolve within the claimed anchor, or be explicitly marked as external/optional | OPEN |
