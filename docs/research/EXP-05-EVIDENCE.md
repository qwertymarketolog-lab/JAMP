# EXP-05 — Evidence Record

## 1. Claim under test

Whether the frozen Run Core v0.3 can represent a bounded interaction between an agent and an independently modeled stochastic environment while preserving deterministic replay, one Run Step per complete interaction, explicit intended-vs-actual outcome distinction, complete event provenance, and an unchanged Run Core.

This record does not claim universal stochastic-system support.

## 2. Frozen anchors

- Protocol: `docs/research/EXP-05-SPEC.md`
- Scenarios: `docs/research/EXP-05-SCENARIOS.md`
- Run Core Git blob SHA-1: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Experiment ref: `feature/exp-05-stochastic-gridworld`

## 3. Implementation

- Adapter: `tests/research/stochastic_gridworld_adapter.py`
- Adapter blob: `907ecd9f257b338bf0dd1413edafefc3129ec960`
- Test: `tests/research/test_exp05_stochastic_gridworld.py`
- Test blob: `a6e18f6b2774981bd535a1cc3c68501af6e3aec7`
- Workflow: `.github/workflows/exp-05-stochastic-gridworld.yml`
- Workflow blob: `4547902d5f7ead17215dc27af52af20fe210b5aa`
- Execution commit: `df93172980c365eea9b370cf06a1de5bfbd36694`

The implementation adds no change to `src/jamp/run.py`. The dedicated workflow independently verifies the Core blob SHA-1 before running the experiment tests.

## 4. CI execution

Dedicated workflow run: `35020257179`

Result:

```text
Run Core blob SHA-1: 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a
.... [100%]
4 passed in 0.04s
```

The four tests cover Core immutability, EXP-05A seed-1 atomic stochastic interaction, EXP-05B per-seed replay determinism, and complete atomic provenance/source attribution.

## 5. Observed stochastic behavior

Using the frozen PRNG and six fixed `MOVE_EAST` intentions:

### Seed 1

Actual outcomes: `E, E, E, E, S, E`.

The fifth interaction is a genuine deviation (`MOVE_EAST` intended, `MOVE_SOUTH` actual). The resulting southward movement is boundary-blocked, so the position remains `(2, 0)`. This event still records the attempted environment outcome separately from the resulting state.

### Seed 2

Actual outcomes: `E, E, E, E, E, N`.

The first five interactions match the intended action. The sixth is an observed environment deviation to `MOVE_NORTH`, producing position `(2, 1)`.

Cross-seed trajectory difference is recorded as an observation only; it is not a pass/fail criterion.

## 6. Atomicity

For both tested seeds:

- `result.steps == 6`
- six provenance events are present
- each event represents one complete `agent intention → environment outcome → new state` transition
- no `INTENT_STEP` / `RESOLVE_STEP` service states are introduced.

## 7. Replay determinism

- Seed 1 run 1 == Seed 1 run 2: PASS
- Seed 2 run 1 == Seed 2 run 2: PASS

Equality covers the complete final state, including event provenance and PRNG state.

## 8. Provenance

Each event explicitly records:

- `state_before`
- `intended_action`
- `intended_by = agent`
- `actual_outcome`
- `outcome_from = environment`
- `is_deviated`
- `state_after`
- `blocked`

The event chain is linked because each event's `state_before` equals the previous event's `state_after`, and the final event's `state_after` equals the returned Run state snapshot.

## 9. Outcome

**TARGET PASS.**

The frozen stochastic agent/environment forcing case is representable by the existing Run Core without modifying `src/jamp/run.py`. One Run Step can contain the complete stochastic interaction, intended and actual outcomes remain semantically distinct, provenance reconstructs the interaction, and fixed seeds replay identically.

## 10. Boundary of the result

This experiment does not establish universal stochastic support, universal POMDP/game support, external real-world integration, parallel/distributed execution, continuous state/action support, or universal problem solving.

A repository-wide full-suite run on this branch also encountered an unrelated pre-existing Q3b production-integration JSON-serialization failure (`tests/research/test_q3b3_production_integration.py`), after 1070 tests passed. That failure is outside EXP-05's dedicated execution criterion and did not affect the dedicated EXP-05 run above.
