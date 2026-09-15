# EXP-05 — Stochastic Gridworld / Agent–Environment Boundary

**Status:** SPECIFICATION FROZEN — no implementation yet

## 1. Research question

Can the current `C_seq` execution model represent an interaction between an agent and an independently modeled stochastic environment while preserving:

- deterministic auditability;
- `1 Run Step = 1 atomic interaction`;
- an explicit distinction between the agent's intended action and the environment's actual outcome;
- an unchanged Run Core?

The experiment is a forcing-case test of the boundary of `C_seq`, not another domain-adapter demonstration.

## 2. Core anchor

The experiment MUST execute against the frozen Run Core blob:

```text
0fee0e1c5c1a1548361965ac51eacdeba62bfe8a
```

`src/jamp/run.py` MUST NOT be modified for EXP-05.

## 3. Minimal environment

### 3.1 Grid

A fixed `3 × 3` grid with boundaries.

- Start: `(0, 0)`
- Goal: `(2, 2)`

Coordinates and boundary behavior are part of the adapter specification.

### 3.2 State

The adapter-owned state contains:

```text
(agent_pos, rng_state, step_count, events)
```

where `rng_state` is a deterministic PRNG state sufficient to reproduce the stochastic sequence exactly.

The precise PRNG representation is an implementation detail, provided that the complete state needed for reproducibility is captured.

### 3.3 Intended actions

The agent's candidate/action space is:

```text
MOVE_NORTH
MOVE_SOUTH
MOVE_EAST
MOVE_WEST
```

`candidates(state)` represents the agent's intended actions. It MUST NOT expose the environment's stochastic outcome as an agent choice.

## 4. Environment transition rules

For each intended movement:

- `P = 0.8`: actual movement follows the intended direction.
- `P = 0.1`: actual movement is a perpendicular deviation to the left.
- `P = 0.1`: actual movement is a perpendicular deviation to the right.

The left/right deviation is defined relative to the intended direction, so the same rule applies symmetrically to all four cardinal directions.

If the actual movement would cross a grid boundary, the agent remains in its current position. The provenance MUST still preserve the attempted actual movement and the fact that the resulting position was blocked by the boundary.

## 5. Intent versus outcome

The central semantic distinction of EXP-05 is:

```text
INTENDED ACTION ≠ ACTUAL OUTCOME
```

whenever the environment deviates from the agent's intention.

The adapter MUST NOT relabel an environment response as an agent action merely to fit the existing execution interface.

The conceptual transition being tested is:

```text
Agent intent
     ↓
Environment response
     ↓
New state
```

## 6. Atomic provenance invariant

Every recorded event MUST contain enough information to reconstruct one complete interaction:

```text
state_before
intended_action
actual_outcome
is_deviated
state_after
```

`is_deviated` MUST be `True` exactly when the actual outcome differs from the intended action.

The provenance representation MUST preserve the distinction between the source of the intention (agent) and the source of the outcome (environment).

## 7. Reproducibility requirement

A run with a fixed initial state and fixed PRNG state MUST be reproducible.

For a repeated execution with the same initial conditions, the following MUST match exactly:

- sequence of intended actions;
- sequence of actual outcomes;
- deviation flags;
- resulting states;
- event provenance.

A different seed MAY produce a different trajectory. This is not itself a failure: the requirement is deterministic reproducibility **conditional on the same initial PRNG state**.

## 8. Experimental modes

### EXP-05A — Fixed-seed stochastic episode

Run a fixed scenario with a fixed initial PRNG state and deliberately chosen agent intentions sufficient to produce at least one observable deviation between intended and actual outcome.

The test asks whether one complete stochastic interaction can be represented and audited as one Run Step without modifying the Core.

### EXP-05B — Seed variation

Repeat the same scenario with a different initial PRNG state.

The test asks whether changing the stochastic source can change the trajectory while preserving the same provenance and reproducibility contract for each individual seed.

EXP-05B MUST NOT require two different seeds to produce different trajectories unless the chosen seeds actually do so under the frozen environment model; seed variation tests the contract, not a predetermined trajectory difference.

## 9. Verdict matrix

| Criterion | TARGET PASS | FORCING FAIL |
|---|---|---|
| Run Core | Frozen Core unchanged | Core modification required |
| Step semantics | One Run Step represents `Intent → Outcome → State'` | One agent action requires multiple Core steps to represent the interaction honestly |
| Intent/outcome separation | Intended and actual are explicitly distinct | Environment response is masked as an agent action |
| Provenance | One event reconstructs the complete interaction | Provenance cannot represent the external response without semantic distortion |
| Reproducibility | Same initial state + PRNG state gives identical execution/provenance | Same initial conditions cannot reproduce the execution |

## 10. Interpretation rules

### TARGET PASS

EXP-05 is a TARGET PASS if the adapter can faithfully represent the agent/environment interaction under the existing `C_seq` execution contract, with the frozen Run Core unchanged, one atomic Run Step per complete interaction, explicit intent/outcome provenance, and deterministic replay for fixed initial conditions.

A PASS does **not** mean that stochasticity has been proven universally representable. It establishes only that this bounded agent/environment forcing case is representable by the existing contract.

### FORCING FAIL

EXP-05 is a FORCING FAIL if faithful representation of the frozen scenario requires a new Core-level interaction contract, such as a distinct environment transition primitive, or otherwise requires splitting one semantically atomic agent/environment interaction into multiple Core steps in order to preserve honest provenance.

A FAIL is an architectural boundary result, not an implementation failure.

## 11. Non-claims

EXP-05 does not claim to establish:

- universal stochastic-system support;
- general POMDP support;
- game-theoretic support;
- external real-world environment integration;
- parallel or distributed execution;
- continuous action/state spaces;
- completeness of `C_seq`;
- universal problem-solving capability.

## 12. Freeze rule

This specification is frozen before implementation.

After implementation begins, the adapter, tests, or execution procedure MUST NOT alter the scientific criteria to obtain a preferred result. Any necessary clarification that changes a verdict criterion must be recorded as a protocol revision before the affected experiment is considered closed.

**Current state:** protocol frozen; implementation pending.
