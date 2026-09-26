# EXP-22 Phase 2A — Forced GC Treatment

## Frozen invariants

- `src/jamp/run.py` blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- canonical workload: `EXP-21-PHASE0-G4-CANONICAL-V1`
- workload hash: `f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92`
- graph construction/imports remain outside the timed region
- wall clock: `time.perf_counter_ns`
- CPU clock: `time.process_time_ns`

## Single treatment

Control executes:

`is_acyclic() -> reachable("0")`

Treatment executes:

`gc.collect() -> is_acyclic() -> reachable("0")`

The GC policy is not changed. The treatment call is inside the same timed interval, so its cost is intentionally measured as part of the treatment.

Python documents `gc.collect()` without arguments as a full collection. The return value is retained as independent treatment observability.

## Design

- 50 paired control/treatment observations.
- Deterministic alternation of within-pair order.
- Raw observations retained.
- Independent GC counters and `gc.collect()` return value retained.
- Paired deterministic sign-permutation test, 20,000 permutations, seed `2202`.
- Distribution-shift threshold: `p < 0.01`.
- No claim of historical G4 causality from this experiment alone.

## Interpretation

A reproducible treatment/control distribution shift is classified as `PERTURBATION_ASSOCIATED`.

It does **not** establish `G4_ROOT_CAUSE`.

Historical signature matching is explicitly `NOT_TESTED` in Phase 2A and must remain so unless independent historical evidence is available.
