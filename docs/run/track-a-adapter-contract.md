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

### Equivalence gate result

Adapter equivalence gate: **PASS, 15/15**.

- Cases: roots `{2,3,5}` × seeds `{0,1,2,42,99}`
- Anchor: `track_a/common.py @ 4b8aa64e` (direct run)
- Adapter: `tests/research/track_a_run_adapter.py`
- Gate: `tests/research/test_track_a_equivalence.py`
- Executed on: `5155bc3c547530db53380ef06d677ae7a18e206a`
- Environment: Python 3.14.6, Linux 4.19.111-27127798 aarch64 Android
- Verified (15/15):
  - final object set equality (order-independent)
  - stop reason mapping `MAX_ITERATIONS → budget`
  - `iterations == 500`
  - `steps == 4`
  - `final_size == 13`
- Not compared:
  - Track A `steps` (`len(history) == 13`) vs `RunResult.steps` (`4`) — documented D8 divergence

The pytest invocation reported one test, but that test contains all 15 root × seed equivalence cases.

The later exporter commit `da3afffa34ce95ab1ab3d8ec522b7c104f33e5f3` is not the execution anchor for the 15/15 gate; it contains the exporter used to generate the separate single-run `run_result.json` artifact.

## Non-goals

This contract does not:

- redefine Track A semantics;
- change the Track A engine;
- adapt the random/baseline strategy;
- claim equivalence before the adapter and equivalence gate have been executed;
- treat historical Track A `steps` as `RunResult.steps`.
