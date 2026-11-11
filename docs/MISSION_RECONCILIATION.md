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
| 5 | Task isolation | **DEFERRED** | No `src/jamp/p18/task_family_isolation.py` or other current-main P18 task-family isolation implementation is present in the audited source tree. `src/jamp/research/session.py` provides immutable session/artifact indexing, but does not by itself establish family-scoped access isolation. | **Documentation conflict:** `docs/evidence/README.md` and `status/milestone-matrix.md` describe P18.2 as closed, while its implementation is absent from this current-main tree. Historical/external implementation provenance was not resolved in this audit. |
| 6 | Controlled knowledge transfer | **DEFERRED** | No `src/jamp/p18/controlled_transfer.py` or equivalent current-main cross-task authorization/projection implementation was found in the audited source tree. | **Documentation conflict:** `docs/evidence/README.md` and `status/milestone-matrix.md` describe P18.3 as closed, including explicit authorization and provenance. That documentation alone does not establish that the mechanism is present in current main. |
| 7 | Causal ablation | **DEFERRED** | No current-main P18.4 implementation/test pair was found in the source tree. `src/jamp/research/causal.py` models causal events and ordering, not guardrail-removal experiments. | `docs/milestones/P18.4.md`, `docs/evidence/README.md` and `status/milestone-matrix.md` explicitly keep P18.4 **PENDING VERIFIED CI** and point to target SHA `7b717a8dea269bc5c33d9c128634f55c0bad27b0`. The documented target is not the audited main SHA. |
| 8 | Evidence first | **PRESERVED** | `src/jamp/db/schema.sql` — ordered `evidence_chain` with payload hashes; `src/jamp/db/verdicts.py` — evidence-chain retrieval; `src/jamp/evidence/checker.py` — raw-response digest validation and CHECKED/FAILED/INCONCLUSIVE outcomes; `src/jamp/runtime/evidence_gate.py` — canonical evidence cardinality/hash/Frozen Core checks; `src/jamp/runtime/provenance.py` — execution trace and evidence binding. | The evidence-first principle has concrete persistence, checking and runtime-gate implementations. The research protocol's broader milestone-GREEN rule also depends on CI/evidence workflow controls, not on the database table alone. |

## Reconciliation summary

- **PRESERVED:** 1–4 and 8 — five principles have identifiable implementation in current main, within the stated boundaries.
- **DEFERRED:** 5–7 — three principles are not established by current-main code inspection.
- **ABANDONED:** none identified. No explicit abandonment decision was found; missing implementation is not proof of abandonment.

### Material discrepancy requiring separate resolution

The P18 documentation records P18.2 and P18.3 as closed and names historical implementation commits/CI runs. However, the audited current-main tree does not contain the cited `src/jamp/p18/` implementation files. This audit does not silently resolve that contradiction. It remains **AMBIGUOUS** whether those implementations were removed, live in another repository/branch, or are represented by stale milestone documentation. A separate provenance/history investigation is required before changing the historical milestone claims.

P18.4 is different: the current documentation itself says the milestone remains pending verified CI. It is therefore DEFERRED here, not abandoned and not preserved as a completed capability.

## Interpretation boundary

This document establishes an implementation map, not a verdict that JAMP has or has not pivoted. The count of preserved principles is not a valid decision threshold by itself: the three deferred principles include capabilities that may be absent from current main but documented as completed elsewhere. First resolve the P18 source/provenance conflict; then decide whether the current architecture represents continuation, deliberate narrowing, or a pivot.

No charter, commercial direction, Code Trust Report, checker migration, or product decision is made here.

## Sources

- First substantive README: commit `8c61cd3d1756`, `README.md`.
- Research protocol: `docs/research-protocol.md`.
- Current architecture map: `docs/architecture/README.md`.
- Current milestone/evidence claims: `docs/evidence/README.md`, `status/milestone-matrix.md`, `docs/milestones/P18.4.md`.
- Audited source revision: `9d41f43af9af2292fe5b47e179bdbcf8c6789a70`.
