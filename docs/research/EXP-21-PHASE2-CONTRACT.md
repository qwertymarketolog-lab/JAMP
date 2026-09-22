# EXP-21 Phase 2 — Controlled Scheduling Experiment Contract

Status: OPEN / CONTRACT-ONLY

## 1. Scope

This contract defines a research-only controlled experiment for the remaining G4 root-cause UNKNOWN space.

It tests whether an externally controlled CPU-affinity intervention produces a reproducible change in the canonical G4 wall-time measurement.

Production behavior is not modified.

Required invariants:

- `src/jamp/run.py` remains byte-for-byte unchanged.
- Frozen Core blob remains `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
- G4 threshold remains `T_wall <= 15.000 ms`.
- Canonical workload identity remains `EXP-21-PHASE0-G4-CANONICAL-V1`.
- Workload definition hash remains `f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92`.

This document is a contract, not execution evidence. No result is implied by the existence of this file.

## 2. Hypotheses

### H0

A controlled CPU-affinity intervention does not produce a reproducible change in paired `T_wall`.

### H1

A controlled CPU-affinity intervention produces a reproducible change in paired `T_wall`.

A supported H1 establishes an effect of the specified intervention. It does not by itself establish hypervisor scheduling as the underlying mechanism.

## 3. Conditions

Each pair contains exactly one CONTROL and one TREATMENT observation.

CONTROL:

- default process CPU affinity;
- no affinity intervention;
- canonical workload and measurement procedure.

TREATMENT:

- process CPU affinity explicitly restricted to one CPU;
- actual post-intervention affinity must be observed and recorded;
- the selected CPU must be valid for the runner;
- all other workload and measurement rules remain identical.

Requested affinity is not evidence of applied affinity. A pair is invalid unless observed affinity proves the treatment condition.

## 4. Pairing and sample size

Primary sample:

- N = 30 valid paired observations.
- Pair order is deterministic and alternates:
  - odd pair: CONTROL -> TREATMENT
  - even pair: TREATMENT -> CONTROL
- A pair with a missing, invalid, or contaminated observation is not silently counted.
- If fewer than 30 valid pairs remain, the experiment is INCONCLUSIVE.

Warm-up policy, workload initialization, measurement boundaries, and GC policy must be identical between conditions.

## 5. Statistical criterion

Primary effect:

`Delta_i = T_wall(TREATMENT)_i - T_wall(CONTROL)_i`

Primary test:

- Wilcoxon signed-rank test;
- two-sided;
- alpha = 0.01;
- median Delta is reported as an effect-size descriptor.

Causal support requires all of:

1. N = 30 valid pairs;
2. valid provenance for every pair;
3. treatment affinity verified from observation;
4. no contamination/fail-closed violation;
5. Wilcoxon p < 0.01.

If p >= 0.01, the scheduling-intervention effect is NOT_SUPPORTED for this scope.

The G4 contract state is independent: this experiment cannot convert G4 CONTRACT_VIOLATION into PASS.

## 6. Provenance schema

Every observation must record:

- experiment_id = EXP-21-PHASE2-SCHEDULING-V1
- phase = 2
- pair_id
- condition = CONTROL | CPU_AFFINITY
- target_commit
- workload_spec_id
- workload_definition_hash
- experiment_seed
- timestamp
- runner_name
- runner_os
- runner_arch
- kernel
- python_version
- cpu_count_visible
- cpu_affinity_before
- cpu_affinity_after
- affinity_verified
- wall_ms
- cpu_ms
- non_cpu_delta_ms
- gc_enabled
- gc_gen2_collections

The experiment artifact must additionally contain:

- n_pairs
- wilcoxon_p
- alpha
- median_delta_ms
- status
- validation_errors

## 7. Identity binding

The expected target commit is supplied by the execution workflow from the actual pull-request head SHA. A synthetic merge SHA must not be substituted.

The validator must reject:

- missing target commit;
- target commit mismatch;
- missing workload identity;
- workload hash mismatch;
- missing experiment seed;
- missing pair identity;
- unknown condition;
- missing environment identity.

## 8. Fail-closed rules

The validator returns INCONCLUSIVE / invalid evidence if any critical condition fails.

Critical failures include:

- target SHA missing or mismatched;
- canonical workload identity/hash mismatch;
- fewer than 30 valid pairs;
- duplicate pair IDs;
- incomplete pair;
- missing CONTROL or TREATMENT;
- missing or contradictory affinity evidence;
- requested treatment affinity differs from observed affinity;
- missing wall/CPU timing;
- non-finite timing values;
- missing runner/environment identity;
- missing artifact fields;
- unavailable statistical calculation;
- artifact serialization/upload failure.

No fallback, repair, substitution, imputation, or synthetic observation is permitted.

## 9. Interpretation boundary

The experiment distinguishes:

OBSERVED:
G4 wall-time measurements.

VERIFIED:
the intervention was actually applied and the provenance contract passed.

INFERRED:
a statistically supported effect of the specified CPU-affinity intervention.

UNKNOWN:
the lower-level mechanism explaining that effect, including any hypervisor mechanism.

Therefore:

`CPU_AFFINITY_EFFECT = SUPPORTED`

must never be rewritten as:

`HYPERVISOR_ROOT_CAUSE = PROVEN`

## 10. State machine

Initial:

- EXP-21 Phase 2 = OPEN
- Scheduling hypothesis = OPEN
- G4 Gate 1 = CONTRACT_VIOLATION
- G4 root cause = UNKNOWN
- Frozen Core = LOCKED

Terminal experiment states:

- VERIFIED / SUPPORTED
- VERIFIED / NOT_SUPPORTED
- INCONCLUSIVE

No transition is permitted from RUNNING directly to PASS.

## 11. Non-goals

This phase does not:

- change production code;
- change the G4 threshold;
- optimize the workload;
- change graph topology;
- alter GC policy;
- assert hypervisor causality;
- clear G4 independently;
- modify existing experiment verdicts.
