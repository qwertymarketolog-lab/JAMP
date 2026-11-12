# JAMP Mission Reconciliation

**Status:** FACTUAL CODE AUDIT — static inspection  
**Audit date:** 2026-11-12  
**Audited main:** `9d41f43af9af2292fe5b47e179bdbcf8c6789a70`  
**Original principles source:** `README.md` at commit `8c61cd3d1756` (blob `71f278c936aef62856d4406940f8470996109066`)  
**Repository initial commit:** `81965fd321d023c3813bea6687a5ec76d01e4f9c` — initial tree contained only `LICENSE`; it is not the commit containing the first README.

## Method and status semantics

The eight principles below are transcribed from the first substantive README. The current implementation assessment is based on the source tree at the exact `main` SHA above and the named source files. Documentation claims are not treated as proof that code exists.

- **PRESERVED** — a current-main implementation exists in code. Scope limitations are stated.
- **DEFERRED** — no sufficient current-main implementation was found, and no explicit decision to abandon the principle was found.
- **ABANDONED** — an explicit decision to stop pursuing the principle exists. Absence from the current tree is not enough.
  
This is a static code audit. It does not claim that all listed behavior was independently executed in this audit or that current CI is green. The statuses classify implementation presence, not terminal CI verification.

## Principle-by-principle result

| # | Original principle | Status | Current-main implementation evidence | Boundary / finding |
|---|---|---|---|---|
| 1 | Causal Event DAG | **PRESERVED** | `src/jamp/domain/event.py` — immutable `EventNode`, parent IDs and SHA-256 identity; `src/jamp/events/dag.py` — append-only `EventDAG`; `src/jamp/domain/causal.py` — parent validation, cycle detection, deterministic topological order and vector clocks; `src/jamp/research/causal.py` — content-addressed causal events and DAG ordering. | More than a linear log: explicit parent edges and DAG validation are implemented. |
| 2 | Deterministic search | **PRESERVED** | `src/jamp/research/search_space.py` — immutable, content-addressed `SearchState` and validated mutations; `src/jamp/research/candidate_generator.py` — pure candidate generation ordered by state hash; `src/jamp/p17/policy_guided_search.py` — canonical policy-bound trajectory digest. | Bounded deterministic search/generation surfaces exist. This does not establish that every possible JAMP search or external model response is deterministic. |
| 3 | Replay & Time Travel | **PRESERVED** | `src/jamp/domain/replay.py` — `ReplayEngine.replay()` reconstructs Registry state and `replay_until()` reconstructs the ancestry ending at a target event; `src/jamp/p17/policy_replay.py` — deterministic policy-state replay; `src/jamp/research/replay.py` — replay trace verification and lineage-state reconstruction. | Historical reconstruction is implemented for declared event/state contracts; it is not a universal snapshot of arbitrary runtime/process state. |
| 4 | Policy learning | **PRESERVED** | `src/jamp/p17/dynamic_policy.py` — `DynamicPolicyAdaptor.update()` deterministically recalculates weights from evidence while retaining an exploration floor; `src/jamp/p17/policy_event.py` and `policy_replay.py` — immutable policy updates and replay; `src/jamp/p17/closed_loop.py` — experiment loop joining search, evaluation, pattern indexing, policy adaptation and replay. | This is a bounded evidence-driven adaptive policy loop. It is not evidence of general-purpose machine learning, neural-network training or unrestricted reinforcement learning. |
| 5 | Task isolation | **UNVERIFIABLE** | No implementation file exists in the audited current-main tree. The local repository check reported on 2026-11-12 found no object matching the documented production commit prefix `a68bd08b`; GitHub API lookup also returned 422 (no commit found). | Historical forensic branch `audit/p17-restoration-staging` contains a later restoration commit `874c890625a1204f23955bf5033e7acd8e287347`, but this does not verify the claimed P18.2 production milestone or its CI. |
| 6 | Controlled knowledge transfer | **UNVERIFIABLE** | No implementation file exists in the audited current-main tree. The documented production commit prefix `a68bd08b` could not be resolved in the current repository; the operator-reported local object-database checks were empty and GitHub API lookup returned 422. | The historical forensic restoration branch is not evidence that the documented P18.3 production commit was merged or terminal-CI-verified. |
| 7 | Causal ablation | **DEFERRED** | No current-main P18.4 implementation/test pair was found in the source tree. `src/jamp/research/causal.py` models causal events and ordering, not guardrail-removal experiments. | `docs/milestones/P18.4.md`, `docs/evidence/README.md` and `status/milestone-matrix.md` explicitly keep P18.4 **PENDING VERIFIED CI** and point to target SHA `7b717a8dea269bc5c33d9c128634f55c0bad27b0`. The documented target is not the audited main SHA. |
| 8 | Evidence first | **PRESERVED** | `src/jamp/db/schema.sql` — ordered `evidence_chain` with payload hashes; `src/jamp/db/verdicts.py` — evidence-chain retrieval; `src/jamp/evidence/checker.py` — raw-response digest validation and CHECKED/FAILED/INCONCLUSIVE outcomes; `src/jamp/runtime/evidence_gate.py` — canonical evidence cardinality/hash/Frozen Core checks; `src/jamp/runtime/provenance.py` — execution trace and evidence binding. | The evidence-first principle has concrete persistence, checking and runtime-gate implementations. The research protocol's broader milestone-GREEN rule also depends on CI/evidence workflow controls, not on the database table alone. |

## Reconciliation summary

- **PRESERVED observations:** principles 1–4 and 8 have identifiable implementation in current main, within the stated boundaries (5/8).
- **UNVERIFIABLE:** 5–6 — the matrix and evidence README assert historical closure, but the cited production commit and terminal CI evidence cannot be verified in the current repository state.
- **DEFERRED:** 7 — Causal Ablation is not implemented in audited current main and its own milestone documentation remains pending verified CI.
- **ABANDONED:** none identified. No explicit abandonment decision was found; missing implementation is not proof of abandonment.

### P18.2 / P18.3 — historical closure claim is UNVERIFIABLE

The documentation records P18.2 and P18.3 as closed:

- `docs/evidence/README.md` states that P18.1.2, P18.2 and P18.3 are closed.
- `status/milestone-matrix.md` claims 125+ tests for P18.2 and cites production commit `a68bd08b...` plus CI Run #141 (134 passed + P17.6 report success) for P18.3.

Verification evidence recorded on 2026-11-12:

- The operator reports that `git fetch --all --tags` completed.
- The operator reports `git log --all --oneline --grep="a68bd08b"` returned no matches.
- The operator reports `git cat-file -t a68bd08b` returned `fatal: Not a valid object name a68bd08b`.
- The operator reports `git reflog --all` contained no match.
- GitHub API lookup `/commits/a68bd08b` returned HTTP 422, `No commit found for SHA`.
- The cited Run #141 was not identified. A run number without its workflow identity is insufficient to uniquely identify an Actions run and is not terminal Run→Job→Artifact evidence.

The local terminal results above are operator-provided evidence; they were not executed by this audit agent. Taken together with the current-main tree inspection and the GitHub API response, they establish that the cited production commit is not verifiable in the current JAMP repository state. They do not establish that the commit never existed. A force-push, migration, or other history change may explain its absence; no accusation is made.

A separate historical forensic branch contains P18 source files introduced by commit `874c890625a1204f23955bf5033e7acd8e287347`. That is a restoration artifact, not proof of the claimed production commit or its CI, and is not authorized for restoration or merge by this reconciliation.

**Conclusion:** P18.2 Task Isolation and P18.3 Controlled Knowledge Transfer are **UNVERIFIABLE**, not DEFERRED and not ABANDONED. The documentation asserts completion, but the cited production provenance and terminal CI evidence are unavailable in the current repository state.

**Follow-up boundary:**
1. Record P18.2/P18.3 as `CLOSED (unverified, evidence missing)` in the milestone matrix, preserving the historical claim while explicitly withdrawing any implication that it is currently verified.
2. Evaluate restoration from `audit/p17-restoration-staging` only in a separate issue after reviewing commit `874c890`; no restoration is performed here.
3. Treat this as the same documentation/evidence mismatch class as `KNOWN-GAP-G1-ALIAS`: documentation claims must not exceed what the available code and evidence can establish.

## Interpretation boundary

This document establishes an implementation map, not a verdict that JAMP has or has not pivoted. The count of preserved principles is not a valid decision threshold by itself: the three deferred principles include capabilities that may be absent from current main but documented as completed elsewhere. First resolve the P18 source/provenance conflict; then decide whether the current architecture represents continuation, deliberate narrowing, or a pivot.

Final principle count: **5 PRESERVED / 1 DEFERRED / 2 UNVERIFIABLE / 0 ABANDONED**.

No charter, commercial direction, Code Trust Report, checker migration, or product decision is made here.

## Sources

- First substantive README: commit `8c61cd3d1756`, `README.md`.
- Research protocol: `docs/research-protocol.md`.
- Current architecture map: `docs/architecture/README.md`.
- Current milestone/evidence claims: `docs/evidence/README.md`, `status/milestone-matrix.md`, `docs/milestones/P18.4.md`.
- Historical branch/PR evidence: `audit/p17-restoration-staging@7d6aed018092df42d79e38f61cc1bf46249ac5c7`, commit `874c890625a1204f23955bf5033e7acd8e287347`, draft PR #111.
- Audited source revision: `9d41f43af9af2292fe5b47e179bdbcf8c6789a70`.
