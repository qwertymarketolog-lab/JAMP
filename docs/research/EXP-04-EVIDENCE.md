# EXP-04 — Constraint Search Transfer Evidence

Status: **CLOSED — TARGET PASS**

Date: 2026-09-15

## Question

Can Run Core execute a nontrivial CSP search with domain-owned pruning, explicit backtracking, and exhaustive traversal while keeping all CSP semantics inside the adapter and leaving `src/jamp/run.py` unchanged?

## Benchmark

4-Queens CSP, deterministic column order `(1, 2, 3, 4)`.

Modes:

- FIND_ONE — stop after the first solution.
- EXHAUSTIVE — enumerate the complete solution set.

Expected solutions:

- `(2, 4, 1, 3)`
- `(3, 1, 4, 2)`

## Implementation

Execution branch: `feature/exp-04-4queens`

Adapter: `tests/research/queens_adapter.py`

- blob SHA: `f0f210359297abc0e327921599a6b3ff01b08af1`

Tests: `tests/research/test_exp04_4queens.py`

- blob SHA: `74d2249835bf13a78d2ed90d73c539c5de1cf244`

Execution workflow: `.github/workflows/exp-04-4queens.yml`

- blob SHA: `251d1d5f4f93593e784f80dea19f0ea435ca9a3f`

Run Core blob at execution commit:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

The workflow explicitly checked this blob before running the experiment.

## Provenance contract exercised

Each adapter transition records an immutable `Event` containing:

- event kind: `PLACE`, `PRUNE`, `BACKTRACK`, or `TERMINAL_SAT`;
- domain details;
- `board_before`;
- `board_after`.

`PRUNE` records `conflict_with_row`.

The test suite verifies that consecutive events form a continuous board-state chain and that `result.steps == len(events)`, establishing the declared one-step/one-transition mapping for this adapter.

## Execution

Execution commit:

`0b12d63a49cab7fbb804f9fad29a3dbaa68ccb3d`

GitHub Actions workflow run:

`35016967681`

Command:

```text
PYTHONPATH=src:tests/research python -m pytest -q tests/research/test_exp04_4queens.py
```

Recorded execution timestamp:

`2026-09-15T20:00:22Z`

Result:

```text
..                                                                       [100%]
2 passed in 0.02s
```

Execution artifact:

- Name: `exp-04-4queens-execution`
- Artifact ID: `10416510391`
- SHA-256: `3d51ded65b0f5ec6b8f0db057070b903fdee102368c7ac833f7a2fc21d0ce0f5`
- Status observed during audit: not expired

This artifact is the CI execution-metadata artifact. It is **not** an Artifact v0 domain-result envelope. Therefore Artifact v0 envelope neutrality was not independently tested by this EXP-04 execution and is not claimed here.

## Verified outcomes

### EXP-04A — FIND_ONE

PASS.

Verified by test:

- terminal stop;
- exactly one solution;
- solution `(2, 4, 1, 3)`;
- at least one `PRUNE`;
- at least one `BACKTRACK`;
- exactly one `TERMINAL_SAT`;
- every `PRUNE` carries `conflict_with_row`;
- provenance chain is continuous;
- one successful Run step corresponds to one recorded event.

### EXP-04B — EXHAUSTIVE

PASS.

Verified by test:

- terminal stop;
- exactly two solutions;
- exact solution set and deterministic order:
  `(2, 4, 1, 3)`, `(3, 1, 4, 2)`;
- `PRUNE`, `BACKTRACK`, and two `TERMINAL_SAT` events present;
- at least one backtrack originates at depth >= 3;
- at least one immediate `PRUNE -> BACKTRACK` dead-end transition;
- every backtrack moves to a shallower frame;
- provenance board chain is continuous;
- one successful Run step corresponds to one recorded event.

## Outcome matrix

| Criterion | Result |
|---|---|
| Find-one CSP search | PASS |
| Exhaustive CSP search | PASS |
| Explicit pruning | PASS |
| Explicit backtracking | PASS |
| Explicit solution transition | PASS |
| One step = one transition | PASS |
| Provenance state chain | PASS |
| Run Core unchanged | PASS |
| Core breach | FALSIFIED |
| Trivial execution | FALSIFIED |
| Artifact v0 envelope neutrality | NOT TESTED in EXP-04 |

Overall experiment outcome: **TARGET PASS** for the stated CSP execution-transfer question.

## Boundary of the claim

This experiment demonstrates transfer of the existing execution kernel to the tested 4-Queens CSP search pattern. It does **not** establish a universal CSP solver, universal search algorithm, third-domain neutrality, Artifact v0 production-exporter transfer, or general problem-solving ability outside the tested contract.

No modification to `src/jamp/run.py` was required.
