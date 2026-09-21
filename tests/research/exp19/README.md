# EXP-19 Performance Diagnostic

## Scope

This research-only diagnostic profiles the existing EXP-19 adjacency graph without changing production/runtime behavior. The Frozen Core and PR #96 remain untouched.

## Evidence

Commit `41a0d6c175e7748feef623d2d66c8cded27eee8d` passed all five mandatory gates:

- Developer Quality: run `35360737124`
- P20.11: run `35360737166`
- P20.5: run `35360737152`
- P23.0-B: run `35360737277`
- SBOM: run `35360737164`

The diagnostic uses 5 warm-up iterations and 25 recorded iterations. For the GC-control condition, `gc.collect()` is performed before each sample and garbage collection is disabled during the timed build/acyclic/reachable phases, then re-enabled in `finally`.

## Telemetry

Values below are seconds from the DQ job log for run `35360737124`.

| Edges | Acyclic p50 / p95 / p99 | Reachable p50 / p95 / p99 |
| ---: | --- | --- |
| 5,000 | 0.000853 / 0.000878 / 0.000886 | 0.000689 / 0.000752 / 0.000776 |
| 10,000 | 0.001712 / 0.001764 / 0.001767 | 0.001241 / 0.001391 / 0.001425 |
| 20,000 | 0.003629 / 0.003757 / 0.003805 | 0.003139 / 0.003314 / 0.003380 |
| 40,000 | 0.007186 / 0.008132 / 0.008348 | 0.005744 / 0.006315 / 0.006614 |

For the 20,000-edge target, the combined acyclic + reachable medians are approximately 6.77 ms, with p95 approximately 7.07 ms and p99 approximately 7.18 ms.

The preceding GC-enabled profile on commit `fd1252b9fe0c75c177381b0de5c35dfd2d9a8801` measured approximately 13.95 ms combined p50, 15.72 ms p95, and 16.20 ms p99 at 20,000 edges.

## Vector exhaustion ledger

The following records the EXP-19 research conclusions reached on the isolated `tests/research/exp19/` contour. These are diagnostic conclusions for the tested configurations, not universal causal claims.

- **Vector #3 — `sys.setswitchinterval` sweep:** rejected as an explanation for the observed tail behavior; tested tail position/amplitude remained stable.
- **Vector #4 — topology drift:** exhausted for the tested target; `unique_topology_count == 1` at V=20,000 and E=20,000.
- **Vector #5 / #5-B — dispatch/order permutation:** null signal. The multi-seed probe (K=10, N=40, E=10,000) produced confidence intervals crossing zero for the tested dispatch-position and iteration-id correlations.
- **Vector #6 — decoupled allocation/timing probe:** null signal in the tested seed/session. Phase A latency was measured independently from Phase B `tracemalloc` allocation deltas after a 5-iteration warm-up; 35 samples were paired by iteration index. The observed Pearson correlations were approximately -0.023 for allocation bytes and -0.018 for allocation blocks, below the diagnostic `|r| >= 0.3` signal criterion.

### Epistemic interpretation

Across the tested Vectors #3–#6, no systematic signal was detected that justifies a production/runtime modification. The Vector #6 result does not establish causality and does not prove that all residual latency variance is caused by a particular OS or CPython mechanism. It only reports a null allocation-latency correlation for the tested configuration.

Accordingly, EXP-19 is marked **EXHAUSTED** for the tested hypothesis vectors. Further probing requires a new reproducible symptom or a new falsifiable hypothesis.

## Contract and core invariants

- No production threshold or Frozen Core code is changed by this research.
- `src/jamp` remains unchanged by the EXP-19 vector probes.
- The 15.000 ms contract remains locked; no production threshold adjustment is made as part of this closure.
- Research artifacts remain isolated under `tests/research/exp19/` and their CI evidence remains in Git history.

## Closure

The EXP-19 research cycle is considered **EXHAUSTED** on this branch after the Vector #6 diagnostic and mandatory CI verification. PR #123 is to be closed without merge so that the research branch and its CI evidence remain preserved in Git history.
