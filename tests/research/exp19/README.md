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

## Interpretation

The GC-disabled run shows substantially lower timing tails and approximately linear growth across the tested 5k–40k range. This is evidence against an algorithmic scaling degradation in the tested range and supports an environment/GC contribution to the earlier contract failure.

This is not a universal proof of asymptotic complexity or a proof that GC is the sole source of all runner variance. The comparison consists of separate CI runs, so runner noise remains a possible contributor.

## Contract handling

No production threshold or Frozen Core code is changed by this diagnostic. The existing EXP-19 contract remains the subject of a separate decision based on this evidence.
