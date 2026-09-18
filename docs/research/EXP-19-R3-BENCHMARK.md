# EXP-19.R3 — G-Scale Benchmark

## Status

RED / baseline protocol artifact.

This document defines the empirical measurement protocol. It does not define
a latency threshold and does not promote performance measurements into a
functional contract.

## Scope

- Branch: `research/exp19-r3-benchmark`
- Seed: `42`
- Vertices: `10,000`
- Edges: `20,000`
- Samples: 10 per operation and profile
- Warm-up: 1 per operation and profile
- Clock: `time.perf_counter_ns()`

## Profiles

1. `single` — 100% CTRL
2. `mixed` — deterministic uniform distribution across DEP/REF/DATA/CTRL
3. `rare` — CTRL < 1% of edges
4. `dominant` — CTRL > 95% of edges
5. `empty` — 0 CTRL edges
6. `near-complete` — dense relation subset over a bounded vertex region

The generator uses forward-only edges to keep the generated topology acyclic
while preserving deterministic G-scale size.

## Operations

For every profile:

- `subgraph_view("CTRL")`
- `is_acyclic()` on the resulting view
- `reachable(representative_node)` on the resulting view

No latency assertion is made during RED/baseline collection.

## Evidence schema

The generated `benchmark.json` contains:

- experiment/protocol identifiers;
- seed and graph dimensions;
- profile and operation for every measurement;
- all 10 raw nanosecond samples;
- min, max, median, mean and p95;
- Python/platform/CI runner metadata.

The JSON file is runtime evidence. It is written locally under
`artifacts/exp19-r3/` and is intended to be uploaded by CI as an Actions
artifact rather than committed to Git.

## Invariants

- `src/jamp` delta: 0.
- `ObservationRelation` delta: 0.
- Existing functional tests remain separate from the performance benchmark.
- No R3 performance threshold is introduced before baseline evidence exists.
