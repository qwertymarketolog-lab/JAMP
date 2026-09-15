# EXP-04 — B-audit

Date: 2026-09-15

Audit criterion: the evidence chain must be reconstructible from `main → docs/research/evidence-index.md → exact ref → exact evidence path`, without relying on arbitrary history or unstated context.

## Canonical path

1. `main`
2. `docs/research/evidence-index.md`
3. Ref: `feature/exp-04-4queens`
4. Evidence: `docs/research/EXP-04-EVIDENCE.md`
5. Evidence blob: `8ea4ce018edd14d854b706a3518b4006df50e4a3`

The main index records the exact ref, evidence path, execution commit, Core blob, adapter/test/workflow blobs, CI run, and execution artifact. The index itself is published on main at commit `5a8f38ae79b1c4e4d160e959b86c433a26bfc7f7`.

## Six-question audit

### 1. Claim — PASS

EXP-04 claims a bounded transfer result: the tested 4-Queens CSP search pattern can execute through Run Core v0.3 without modifying `src/jamp/run.py`, with CSP semantics retained in the adapter.

The evidence explicitly limits the claim and does not claim a universal CSP solver or general problem-solving ability.

### 2. Anchor — PASS

Executed-on commit:

`0b12d63a49cab7fbb804f9fad29a3dbaa68ccb3d`

Run Core blob at execution:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

The workflow independently checked the Core blob before running the tests. The adapter, test, and workflow blobs are also recorded in the evidence and resolve at the execution commit.

### 3. Code — PASS

Exact execution blobs:

- adapter: `f0f210359297abc0e327921599a6b3ff01b08af1`
- test: `74d2249835bf13a78d2ed90d73c539c5de1cf244`
- workflow: `251d1d5f4f93593e784f80dea19f0ea435ca9a3f`

The adapter owns Frame state, pruning, backtracking, solution handling, and event provenance. No CSP-specific mechanism was added to Run Core.

### 4. Test — PASS

CI workflow run: `35016967681`.

Command:

`PYTHONPATH=src:tests/research python -m pytest -q tests/research/test_exp04_4queens.py`

Recorded result: `2 passed in 0.02s`.

This is identified as a GitHub Actions CI execution, not a local run.

### 5. Result — PASS

EXP-04A FIND_ONE produced exactly one solution: `(2,4,1,3)`.

EXP-04B EXHAUSTIVE produced exactly two solutions, in deterministic order:

`(2,4,1,3)` and `(3,1,4,2)`.

The tests also verify PRUNE, BACKTRACK, TERMINAL_SAT, continuous board provenance, and one-step/one-event correspondence.

Execution artifact:

- ID: `10416510391`
- SHA-256: `3d51ded65b0f5ec6b8f0db057070b903fdee102368c7ac833f7a2fc21d0ce0f5`
- observed status at audit time: not expired

Important scope distinction: this is a CI execution-metadata artifact, not an Artifact v0 domain-result envelope. Artifact v0 envelope neutrality was therefore not tested by EXP-04 and is not used as evidence for the CSP transfer claim.

### 6. Outcome — PASS

Recorded outcome: **TARGET PASS**.

Auditable formulation:

> EXP-04 confirms CSP search as an instance of C-seq. Core unchanged. Class boundary not shifted.

This is a coverage confirmation, not a claim that JAMP is now a universal constraint-search or CSP solver.

## Final B-audit result

**PASS — RECONSTRUCTIBLE.**

All six required evidence questions are independently reconstructible from the canonical publication path. The separately noted Artifact v0 envelope neutrality gap does not invalidate the stated EXP-04 CSP execution-transfer claim because that property is explicitly outside the tested scope.
