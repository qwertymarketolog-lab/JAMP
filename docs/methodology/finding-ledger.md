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
| M-006 | static code reading treated as source of truth | S0+ count. Static reading produced 10; local execution produced 9. | execution verification against frozen code | integrity gap was flagged as `9 vs 10` when only 9 was correct; one reading error propagated into characterization status | static reading is a hypothesis about code, not a measurement of it. Any count derived by reading must be labeled UNVERIFIED until reproduced by execution or by an independent reader. | ADDRESSED (reproduced 2026-09-12) |
| M-008 | structural substitution convergence | H-J2 partial: C1 and C2 established for current vocabulary @ `d1b3a8c` | formal code reading | substitution-layer convergence is structural, not empirical, under the stated conditions | general characterization remains open; if `pow(var,1)` can be constructed C2 breaks; if a source with `repl=var` appears C1 breaks | ESTABLISHED (C1, C2; current vocabulary) |
| M-009 | claimed-but-unverified status | P24-B was previously asserted CLOSED without repository evidence; primary-source audit followed workflow → branch → commit → check-run → run → artifact → digest | primary source audit | status claim was downgraded to NOT-DETERMINED until execution evidence was found, then verified as VERIFIED-SUCCESS | workflow existence and artifact upload (`if: always()`) are not evidence of success; primary evidence requires run conclusion plus artifact identity/digest. P24-B execution is VERIFIED-SUCCESS, while its scientific hypothesis status is MIXED: F1 FALSIFIED; F2 FALSIFIED; F3 SUPPORTED; F4 INCONCLUSIVE; F5 FALSIFIED | ADDRESSED |
| M-010 | partial verification — control broken, treatment observable | P18.4 Run #165: baseline authorization FAIL on fixture; five remaining P18.4 tests PASS by reconciliation | primary workflow logs + pytest summary arithmetic (`140 = 139 + 1 + 0`) | ablation observations exist without a valid baseline control; P18.4 cannot be closed despite the three ablation observations being present | partial verification is not the same as partial success: treatment observations without a valid control cannot establish the causal guardrail claim. PASS-by-reconciliation must remain distinguished from direct per-test evidence | ADDRESSED (P18.4 = VERIFIED-PARTIAL; CLOSED = NO) |
| M-011 | structural boundary finding | H-P1 formalization cannot be expressed in current JAMP vocabulary | Task 1.1 vocabulary audit + Task 2 component comparison | H-P1 not testable on frozen JAMP @ `d1b3a8c` | geometric/temporal hypotheses require a different operator set; extension cycle closed negative | ADDRESSED |
| M-012 | characterization summary | Origin of 13 — characterization components | Track A audit | no single document asserts whole characterization; evidence is split across two repository artifacts and one issue comment | characterization evidence must preserve the distinct execution and provenance levels of its components | ADDRESSED |
| M-013 | structural finding, evidence-pending | H-J1 refined: substitution-layer has unique fixpoint for root=2, source p=2·k_6, vocabulary @ `d1b3a8c` | structural analysis | finding exists but cannot be cited from repository | repository write-up is required to raise evidence level; until then the finding remains session-only | OPEN — requires repository write-up to raise evidence level, or explicit acknowledgment as session-only in downstream documentation |

M-011
Title: H-P1 structural negative
Mode: structural boundary finding
Instance: H-P1 formalization cannot be expressed in current JAMP vocabulary
Detected by: Task 1.1 vocabulary audit + Task 2 component comparison
Evidence: Issue #40 comment 5646491353
Evidence level: issue-comment
Basis: all mandatory components of H-P1 (S₀, F, M, C, X) lie outside frozen vocabulary @ d1b3a8c
No run performed. Static analysis only.
Consequence: H-P1 not testable on frozen JAMP @ d1b3a8c
Generalization: geometric/temporal hypotheses require a different operator set; extension cycle closed negative
Status: ADDRESSED

M-012
Title: Origin of 13 — characterization components
Mode: characterization summary
Evidence (three components, distinct levels):

a) 30-run reproduction
   Evidence: commit 4f5bbc47 + docs/replication/2026-09-12-track-a-experiment-reproduction.md
   Evidence level: repository-artifact
   Scope: ROOTS=(2,3,5) × 5 seeds × 2 strategies = 30 runs
   Result: final_size = 13 in 30/30
   Note: isolated execution of frozen source, not canonical CI.
         Does NOT constitute expanded R_test characterization.

b) S0+ = 9
   Evidence: commit d7e28e6 + docs/replication/2026-09-12-track-a-s0plus.md
   Evidence level: repository-artifact
   Result: AFTER_INIT = 6, AFTER_FIRST_CLOSURE = 9
   Note: isolated execution; run() and substitution not performed.

c) Characterization status: VALID
   Evidence: Issue #40 comment 5646317280
   Evidence level: issue-comment
   Scope: S0+ reproduced, integrity gap resolved

Consequence: no single document asserts whole characterization.
             Evidence is split across two repository artifacts and one comment.
Status: ADDRESSED

M-013
Title: H-J1 refined (branch-scoped substitution convergence)
Mode: structural finding, evidence-pending
Instance: substitution-layer has unique fixpoint for root=2, source p=2·k_6, vocabulary @ d1b3a8c
Basis: source pool stable, target pool stable, novelty monotonically consumes 4 novel pairs, order-independent.
Evidence: NONE in repository or Issues.
Evidence level: session-only
Not subsumed by M-008 (M-008 covers H-J2 partial, not H-J1 refined).

Consequence: finding exists but cannot be cited from repository.
             Cannot be written into STATUS.md with repository reference.
Status: OPEN — requires repository write-up to raise evidence level to repository-artifact, or explicit acknowledgment as session-only in downstream documentation.
