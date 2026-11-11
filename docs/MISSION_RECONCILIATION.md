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
| 5 | Task isolation | **AMBIGUOUS** | The file is absent from audited `main`, but exists on the historical `audit/p17-restoration-staging` branch at head `7d6aed018092df42d79e38f61cc1bf46249ac5c7` (blob `1e6660ef6f69294cfea9b85a81e319fbfba97c67`). It was introduced by commit `874c890625a1204f23955bf5033e7acd8e287347` (`forensic: restore historical JAMP promotion gap for CI validation`) and is included in open draft PR [#111](https://github.com/qwertymarketolog-lab/JAMP/pull/111). | This proves a branch/PR implementation exists, not that the documented P18.2 production implementation was merged or terminal-CI-verified. PR #111 remains open, draft, and unmerged; its branch is 8 commits ahead and 1309 behind current `main`. The `125+ tests` claim in `status/milestone-matrix.md` is not independently tied here to terminal CI evidence. |
| 6 | Controlled knowledge transfer | **AMBIGUOUS** | The file is absent from audited `main`, but exists on `audit/p17-restoration-staging` at head `7d6aed018092df42d79e38f61cc1bf46249ac5c7` (blob `10661adda8091a155aeef6e81769752bdb46f63a`). It was introduced by the same forensic restoration commit `874c890625a1204f23955bf5033e7acd8e287347` and is included in open draft PR [#111](https://github.com/qwertymarketolog-lab/JAMP/pull/111). | This proves a branch/PR implementation exists, not that the documented P18.3 production implementation was merged or terminal-CI-verified. PR #111 remains open, draft, and unmerged; its branch is 8 commits ahead and 1309 behind current `main`. The matrix cites only abbreviated production SHA `a68bd08b...` and CI Run #141; the abbreviated SHA cannot identify a commit unambiguously, and no terminal Run→Job→Artifact evidence was established in this investigation. |
| 7 | Causal ablation | **DEFERRED** | No current-main P18.4 implementation/test pair was found in the source tree. `src/jamp/research/causal.py` models causal events and ordering, not guardrail-removal experiments. | `docs/milestones/P18.4.md`, `docs/evidence/README.md` and `status/milestone-matrix.md` explicitly keep P18.4 **PENDING VERIFIED CI** and point to target SHA `7b717a8dea269bc5c33d9c128634f55c0bad27b0`. The documented target is not the audited main SHA. |
| 8 | Evidence first | **PRESERVED** | `src/jamp/db/schema.sql` — ordered `evidence_chain` with payload hashes; `src/jamp/db/verdicts.py` — evidence-chain retrieval; `src/jamp/evidence/checker.py` — raw-response digest validation and CHECKED/FAILED/INCONCLUSIVE outcomes; `src/jamp/runtime/evidence_gate.py` — canonical evidence cardinality/hash/Frozen Core checks; `src/jamp/runtime/provenance.py` — execution trace and evidence binding. | The evidence-first principle has concrete persistence, checking and runtime-gate implementations. The research protocol's broader milestone-GREEN rule also depends on CI/evidence workflow controls, not on the database table alone. |

## Reconciliation summary

- **PRESERVED observations:** principles 1–4 and 8 have identifiable implementation in current main, within the stated boundaries. Do not aggregate this into a “5/8 preserved” mission verdict while principles 5–6 remain AMBIGUOUS.
- **AMBIGUOUS:** 5–6 — branch/PR implementations exist, but their relationship to the documentation's claimed production milestones and current main is unresolved.
- **DEFERRED:** 7 — Causal Ablation is not implemented in audited current main and its own milestone documentation remains pending verified CI.
- **ABANDONED:** none identified. No explicit abandonment decision was found; missing implementation is not proof of abandonment.

### Unresolved: P18.2 / P18.3 documentation gap

The P18 documentation records P18.2 and P18.3 as closed:

- `docs/evidence/README.md`: P18.1.2, P18.2 and P18.3 are stated closed.
- `status/milestone-matrix.md`: P18.2 claims 125+ tests and adversarial isolation vectors; P18.3 claims explicit authorization, source/target integrity, provenance, production commit `a68bd08b...` and CI Run #141.

The audited `main@9d41f43af9af2292fe5b47e179bdbcf8c6789a70` contains neither implementation file.

The investigation found a concrete branch-only implementation:

1. Both files exist on `audit/p17-restoration-staging` at head `7d6aed018092df42d79e38f61cc1bf46249ac5c7`:
   - `src/jamp/p18/task_family_isolation.py`, blob `1e6660ef6f69294cfea9b85a81e319fbfba97c67`.
   - `src/jamp/p18/controlled_transfer.py`, blob `10661adda8091a155aeef6e81769752bdb46f63a`.
2. The path history on that branch attributes both files to commit `874c890625a1204f23955bf5033e7acd8e287347`, message `forensic: restore historical JAMP promotion gap for CI validation` (2026-09-19).
3. Both files are included in draft PR [#111](https://github.com/qwertymarketolog-lab/JAMP/pull/111), which is still open and unmerged. Its head is `7d6aed018092df42d79e38f61cc1bf46249ac5c7`, base SHA is `db74be8baeb321dc4c6453c6e3f0f7a80f7b6300`; comparison with current main reports 8 commits ahead / 1309 behind. This is not a safe merge candidate.
4. The P18.3 production SHA in the milestone matrix is abbreviated as `a68bd08b...`; this investigation did not resolve it to a commit. No terminal CI Run→Job→Artifact evidence for PR #111 was established.

**Conclusion:** this is not “never existed” and not evidence of a merged production implementation. It is **AMBIGUOUS**: code exists in a historical forensic branch/PR, while the documented production closure and current-main presence are unproven. The earlier classification of P18.2/P18.3 as simply DEFERRED would conceal that provenance conflict. Do not merge PR #111 or infer that its old branch can be restored wholesale.

To resolve the original milestone claims, identify the exact production commits and their terminal CI evidence, then determine whether the implementation was later removed, superseded, or never promoted. Until then, P18.2/P18.3 remain AMBIGUOUS.

P18.4 is different: current documentation explicitly keeps it pending verified CI, and no implementation/test pair is present in audited main. It remains DEFERRED, not abandoned.

## Interpretation boundary

This document establishes an implementation map, not a verdict that JAMP has or has not pivoted. The count of preserved principles is not a valid decision threshold by itself: the three deferred principles include capabilities that may be absent from current main but documented as completed elsewhere. First resolve the P18 source/provenance conflict; then decide whether the current architecture represents continuation, deliberate narrowing, or a pivot.

No charter, commercial direction, Code Trust Report, checker migration, or product decision is made here.

## Sources

- First substantive README: commit `8c61cd3d1756`, `README.md`.
- Research protocol: `docs/research-protocol.md`.
- Current architecture map: `docs/architecture/README.md`.
- Current milestone/evidence claims: `docs/evidence/README.md`, `status/milestone-matrix.md`, `docs/milestones/P18.4.md`.
- Historical branch/PR evidence: `audit/p17-restoration-staging@7d6aed018092df42d79e38f61cc1bf46249ac5c7`, commit `874c890625a1204f23955bf5033e7acd8e287347`, draft PR #111.
- Audited source revision: `9d41f43af9af2292fe5b47e179bdbcf8c6789a70`.
