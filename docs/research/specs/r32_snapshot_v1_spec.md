# R32-SNAPSHOT-N1000+ v1

**Status:** Frozen specification candidate  
**Baseline:** `R32-BASELINE-T0`  
**Baseline artifact:** `93e64c6740efb6b06e9416079123f29c6de3a71198826bb3d628d0a4de67bf0f`  
**Baseline commit:** `bbce562d94d4b8545373fc2c0e7bdb9bbd511d25`  
**Frozen Core:** `src/jamp/run.py` blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

## 1. Immutable execution contract

The following fields are part of the comparison identity:

- `immutable_prompt_hash`: SHA-256 of the exact control prompt. Any text change invalidates direct T0→Tn comparison.
- `temperature = 0.0`
- `top_p = 1.0`
- `max_tokens = 512`
- `stream = false`
- `K = 15` repetitions per model/endpoint.
- Round-robin ordering is mandatory: `M1 → M2 → … → MN → M1 …`.
- Each transaction records `provider_model_id`, `endpoint_url`, `timestamp_utc`, `request_hash`, and `raw_response_hash`.

A snapshot is comparable with T0 only when these execution-identity fields match.

## 2. Transport state

For `K=15`:

| Failure rate | Failures | State |
|---|---:|---|
| 0% | 0 | `TRANSPORT_STABLE` |
| >0% and <20% | 1–2 | `TRANSPORT_DEGRADED` |
| ≥20% and <100% | 3–14 | `TRANSPORT_UNSTABLE` |
| 100% | 15 | `UNAVAILABLE` |

A single transport failure is an observation, not by itself a critical breakage.

## 3. Performance drift

Performance comparison is performed only on successful HTTP 2xx transactions and only when T0 and Tn have comparable execution scope.

For P50 and P95 independently:

`shift = abs(Tn - T0) / T0`

If either shift is **>25%**, the evaluation receives `PERFORMANCE_DRIFT`.

A performance change is not interpreted as model drift when execution scope is not comparable; the result is `INCONCLUSIVE`.

## 4. Format contract

A successful transaction passes the format layer only when:

1. response payload is valid JSON;
2. usable answer content is present;
3. the answer contains exactly three numbered points;
4. the three required points correspond to the fixed stimulus contract.

Null content or truncation is recorded as `BEHAVIORAL_DRIFT`, not as semantic correctness.

## 5. Independent semantic reference

Semantic evaluation does not use model consensus as ground truth.

Reference:

- `reference_id = IAU-RES-B5-B6-2006`
- source: International Astronomical Union, Resolutions B5/B6 (2006)

Required facts:

- `orbits_sun`
- `hydrostatic_equilibrium`
- `cleared_neighborhood`

Accepted terminology may include:

- `dwarf planet`
- `карликовая планета`
- equivalent wording expressing that Pluto did not clear its orbital neighborhood.

For this stimulus, `minor planet` as the adopted modern classification of Pluto, `regular planet`, and `asteroid` are forbidden claims.

A semantic evaluator must distinguish factual equivalence from literal string matching. If the evidence is insufficient to determine correctness, state `INCONCLUSIVE`.

## 6. Deterministic evaluation states

```text
Raw transaction matrix
        |
        v
Transport
  |             |
failure       success
  |             |
UNAVAILABLE/   Format
TRANSPORT_*      |
                 +-- null/truncated --> BEHAVIORAL_DRIFT
                 |
                 +-- valid 3 points --> Semantics
                                          |
                              +-----------+-----------+
                              |                       |
                           verified              anomaly
                              |                       |
                           STABLE             SEMANTIC_ANOMALY
```

Performance drift is evaluated separately and can supersede `STABLE` for the corresponding snapshot comparison.

## 7. T0 → Tn comparison

Each comparison records:

- `snapshot_id`
- `baseline_id`
- `timestamp_utc`
- `target_model_id`
- `state_transition`
- transport success-rate delta
- format-compliance delta
- semantic-compliance delta
- P50/P95 latency delta
- evaluation version
- reference version

Allowed state transitions:

- `NO_CHANGE`
- `REGRESSION_TRANSPORT`
- `REGRESSION_FORMAT`
- `REGRESSION_SEMANTICS`
- `IMPROVEMENT_RECOVERY`
- `NEW_ENTRY`

## 8. Evidence rules

- CI success proves execution completion, not model correctness.
- Model consensus is not a semantic reference.
- Missing evidence does not become PASS.
- Conflicting evidence remains a conflict.
- Historical evidence is not silently treated as current evidence.
- Every published state must be reproducible from the raw transaction artifact and this contract version.

## 9. Scope

This specification adds no dependency on the Frozen Core and does not modify `src/jamp/run.py`.

**Freeze condition:** once merged, changes to this contract require a new specification version rather than silent mutation of v1.
