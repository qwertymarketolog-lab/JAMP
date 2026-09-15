# EXP-05 — Test Scenarios A/B

**Status:** SCENARIOS FROZEN — implementation pending

This document defines the concrete execution scenarios for EXP-05A and EXP-05B. It does not modify the frozen research protocol in `docs/research/EXP-05-SPEC.md`.

## 1. Frozen protocol reference

Protocol:

`docs/research/EXP-05-SPEC.md`

Core anchor:

```text
0fee0e1c5c1a1548361965ac51eacdeba62bfe8a
```

The scenarios are subordinate to the protocol. If an implementation detail conflicts with the protocol, the protocol controls the experiment.

## 2. Concrete PRNG test vector

To make the pre-implementation scenarios independently reproducible, the test harness uses the following deterministic PRNG for these scenarios:

```text
x_(n+1) = (1103515245 * x_n + 12345) mod 2^31
u_n = x_n / 2^31
```

The initial integer `x_0` is the scenario seed.

Outcome mapping:

```text
0.0 <= u < 0.8  → intended direction
0.8 <= u < 0.9  → perpendicular deviation to the left
0.9 <= u < 1.0  → perpendicular deviation to the right
```

This concrete PRNG is a test-vector choice, not a claim that EXP-05 requires this particular PRNG implementation in general.

## 3. Action sequence

Both scenarios use the same fixed intended-action sequence:

```text
1. MOVE_EAST
2. MOVE_EAST
3. MOVE_EAST
4. MOVE_EAST
5. MOVE_EAST
6. MOVE_EAST
```

Initial position:

```text
(0, 0)
```

The scenario is deliberately not a shortest-path benchmark. Its purpose is to force observable separation between intended action and environmental outcome while keeping the action policy fixed.

## 4. EXP-05A — Fixed-seed stochastic episode

### Seed

```text
x_0 = 1
```

The first five generated `u` values are:

```text
0.5138700781390071
0.1757413032464683
0.3086515162140131
0.5345338867045939
0.9476279253140092
```

Therefore the fifth interaction is a right deviation from `MOVE_EAST`.

For an eastward intention:

- left deviation = `MOVE_NORTH`;
- right deviation = `MOVE_SOUTH`.

The fifth interaction therefore has:

```text
intended_action = MOVE_EAST
actual_outcome  = MOVE_SOUTH
is_deviated     = True
```

The first four interactions have `actual_outcome = MOVE_EAST` under this fixed vector.

The sixth interaction MUST also be executed and audited; its outcome is determined by the next PRNG value and MUST NOT be hard-coded by the test.

### Required observations

EXP-05A MUST establish all of the following:

1. The Core executes the scenario without modification.
2. Each intended action is selected as an agent action, not as an environment result.
3. At least one event records `intended_action != actual_outcome`.
4. The deviation is explicitly represented by `is_deviated = True`.
5. One complete interaction corresponds to one Run Step.
6. The resulting state and event provenance are reproducible from the same initial state and PRNG state.
7. No environment response is relabeled as an agent action merely to fit the Core interface.

## 5. EXP-05B — Seed variation

Run the identical action sequence and initial position with two seeds:

```text
Seed A = 1
Seed B = 2
```

For seed 2, the first five generated `u` values are:

```text
0.02773440768942237
0.6963285580277443
0.31248870911076665
0.39410713966935873
0.7884873668663204
```

Thus, unlike seed 1, the first five interactions do not contain a stochastic deviation under the frozen mapping. The sixth interaction MUST still be executed and audited.

### Required observations

For each seed independently:

1. Repeating the run with the same initial state and same seed reproduces the complete execution and provenance exactly.
2. Intended actions remain identical between seed A and seed B.
3. The environment outcome is allowed to differ between seeds.
4. The provenance records those outcomes without converting them into agent intentions.
5. A difference between trajectories is not itself a failure; loss of reproducibility for a fixed seed is.

The scenario MUST NOT require a particular trajectory difference beyond what the frozen PRNG vectors actually produce.

## 6. Provenance checks

For every event, the test harness MUST be able to inspect at least:

```text
state_before
intended_action
actual_outcome
is_deviated
state_after
```

The following invariant MUST hold:

```text
is_deviated == (actual_outcome != intended_action)
```

The event sequence MUST remain sufficient to reconstruct the interaction trajectory without treating the environment outcome as a new agent decision.

## 7. Step-count check

For a six-action scenario:

```text
result.steps == 6
```

provided that the existing Run Core's step counter semantics remain the same as in the frozen contract.

No additional `INTENT` or `RESOLVE` service steps may be inserted solely to make the environment interaction representable.

## 8. Replay check

For each seed, execute the exact same initial state twice.

The two executions MUST have identical:

- final state;
- step count;
- intended-action sequence;
- actual-outcome sequence;
- deviation flags;
- event provenance.

Any mismatch is a reproducibility failure under the EXP-05 protocol.

## 9. Boundary check

The implementation is not allowed to declare PASS merely because a stochastic trajectory can be simulated.

The decisive question remains whether the existing Core can represent the semantically complete interaction as:

```text
Intent → Environment Outcome → State'
```

in one atomic Run Step while preserving the intent/outcome distinction.

If that cannot be done honestly without a new Core-level interaction contract or multiple Core steps for one semantic interaction, the result is FORCING FAIL under the frozen protocol.

## 10. No implementation yet

These scenarios are frozen before implementation.

No adapter, test, workflow, or Core modification is implied by this document.

**Current state:** EXP-05A/05B scenarios frozen; implementation pending.
