# Track A Adapter Contract

## Purpose

This document fixes the boundary between the generic `Run` contract and the existing Track A implementation.

The adapter is intended to reproduce the `TREATMENT_TARGETED` Track A semantics. It is not a refactor of Track A itself and does not adapt the baseline/random strategy.

## Source semantics

Track A currently records:

- `steps` as `len(state.history)`;
- closure outputs in `state.history`;
- terminal status from the existing Track A run loop;
- continued looping after an empty target-candidate set, through `s.closure()`.

Therefore Track A metrics must not be silently identified with the generic `Run` metrics.

## D1 — RunResult.steps

`RunResult.steps` is the number of successful `apply` calls performed by `Run`.

For the Track A adapter, this is not the same metric as Track A `steps`.

Track A `steps` is `len(state.history)` and remains available through the returned state.

## D2 — Equivalence

Adapter equivalence compares:

1. final object count (`final_size`);
2. mapped stop reason;
3. final `state.history`.

`RunResult.steps` is not compared with Track A `steps`.

Stop-reason mapping:
- `terminal` ↔ `SOLVED`
- `budget` ↔ `MAX_ITERATIONS`
- `exhausted` ↔ `MAX_OBJECTS` when `on_empty` returns `None`
- `error` ↔ no normal Track A state; adapter error

## D3 — initial

`initial()` constructs the Track A state and performs the initial closure:

```python
s = State(root, max_objects)
s.closure()
return s
```

The same state object is passed onward.

`Run` v0.2 does not require immutable state.

## D4 — candidates

`candidates(state)` delegates to:

```python
target_substitution(state, rng)
```

The adapter creates the RNG at construction and carries it as adapter state.

The candidate order produced by `target_substitution` is deterministic for a given state and RNG state.

## D5 — admissible

`admissible(state, candidate)` returns `True`.

`target_substitution` already performs the relevant novelty filtering.

Any future adapter-specific admissibility filter belongs at this boundary.

## D6 — apply

`apply(state, candidate)` performs the existing Track A mutation and closure:

```python
state.add(candidate.new, candidate.op, candidate.parents)
state.closure()
return state
```

## D7 — on_empty

`on_empty(state)` reproduces Track A recovery semantics:

```python
state.closure()
return state
```

It does not return `None` merely because no new history entry was produced.

Track A continues looping after an empty candidate set until its configured iteration budget is reached or another terminal condition occurs.

Returning `None` here would stop with `exhausted` and would not reproduce Track A.

## D8 — iterations

`RunResult.iterations` is required for the adapter equivalence gate.

It counts loop turns that entered the `Run` body, including `on_empty` recovery turns. The terminal-exit turn is not counted.

`budget` bounds `iterations`, not `steps`.

This keeps three distinct metrics separate:

- `RunResult.steps` — successful `apply` calls;
- `RunResult.iterations` — loop turns;
- Track A `steps` — `len(state.history)`.

## Equivalence gate

The adapter is accepted only if, for the agreed test cases, it reproduces:

- the same final object count;
- the mapped Track A stop reason;
- the same final history.

The gate must also verify that the adapter consumes the expected iteration budget where Track A continues through empty-candidate recovery.

## Non-goals

This contract does not:

- redefine Track A semantics;
- change the Track A engine;
- adapt the random/baseline strategy;
- claim equivalence before the adapter and equivalence gate have been executed;
- treat historical Track A `steps` as `RunResult.steps`.
