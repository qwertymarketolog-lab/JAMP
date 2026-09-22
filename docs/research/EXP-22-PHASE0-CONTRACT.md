# EXP-22 Phase 0 — Measurement Boundary Audit Contract

Status: OPEN / CONTRACT-ONLY

## 1. Scope

This contract defines a research-only audit of the G4 measurement boundary.

The purpose is to establish exactly what the current G4 harness observes and records before any causal intervention is introduced.

This phase produces audit evidence only. It does not establish causality and does not clear G4.

Required invariants:

- `src/jamp/run.py` remains byte-for-byte unchanged.
- Frozen Core blob remains `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
- G4 threshold remains `T_wall <= 15.000 ms`.
- Canonical workload identity remains `EXP-21-PHASE0-G4-CANONICAL-V1`.
- Workload definition hash remains `f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92`.
- Target commit is the exact commit supplied by the execution workflow; synthetic merge SHAs are forbidden.

This document is a contract, not execution evidence. No result is implied by the existence of this file.

## 2. Audit question

The audit asks:

> What exact clock, execution boundary, workload identity, process state, and environment metadata define the observed G4 `T_wall` measurement?

The audit must distinguish the measurement itself from any interpretation of its cause.

## 3. Non-causal design

Phase 0 MUST NOT:

- introduce CONTROL/TREATMENT conditions;
- change CPU affinity;
- change GC policy;
- change workload topology;
- substitute a different timing source for the production measurement;
- modify production code;
- alter the G4 threshold;
- claim a causal effect;
- infer a root cause from telemetry alone.

No Wilcoxon test or causal verdict is required in Phase 0.

## 4. Required provenance

Every audit observation must record:

- `experiment_id = EXP-22-PHASE0-MEASUREMENT-BOUNDARY-V1`
- `phase = 0`
- `target_commit`
- `workload_spec_id`
- `workload_definition_hash`
- `experiment_seed`
- `timestamp`
- `runner_name`
- `runner_os`
- `runner_arch`
- `kernel`
- `python_version`
- `cpu_model` when available
- `cpu_count_visible`
- `cpu_affinity`
- `clock_source` / timing API identity
- `clock_resolution` when available
- `wall_ms`
- `cpu_ms`
- `non_cpu_delta_ms`
- `gc_enabled`
- `gc_gen2_collections`
- measurement start/end markers or equivalent boundary metadata

Environment metadata must describe the actual execution environment, not a requested configuration.

## 5. Measurement boundary

The audit must identify, in machine-readable evidence:

1. when workload initialization begins;
2. when the timed region begins;
3. when the timed region ends;
4. whether graph construction is inside or outside the timed region;
5. whether imports are inside or outside the timed region;
6. whether GC activity can occur inside the timed region;
7. whether serialization, logging, artifact creation, or validation is inside the timed region;
8. which clock API produces `T_wall`;
9. which clock API produces `T_cpu`, if applicable;
10. how `non_cpu_delta_ms` is derived.

If any boundary cannot be established from execution evidence, it must be recorded as UNKNOWN rather than inferred.

## 6. Identity binding

The validator must reject evidence with:

- missing target commit;
- target commit mismatch;
- synthetic merge SHA;
- missing workload identity;
- workload hash mismatch;
- missing experiment seed;
- missing runner/environment identity;
- missing measurement boundary metadata.

The expected target commit must come from the actual workflow event context.

## 7. Integrity / fail-closed rules

The audit is INCONCLUSIVE if any critical observation is invalid or missing.

Critical failures include:

- non-finite wall or CPU timing;
- missing timing API identity;
- missing clock resolution when the platform exposes it;
- missing process affinity;
- missing runner identity;
- missing workload identity/hash;
- inconsistent target SHA;
- contradictory timing-boundary metadata;
- artifact serialization or upload failure;
- incomplete audit observation.

No fallback, repair, substitution, imputation, or synthetic observation is permitted.

## 8. Required artifact

The terminal artifact must contain:

- `experiment_id`
- `phase`
- `target_commit`
- `workload_spec_id`
- `workload_definition_hash`
- `experiment_seed`
- `observations`
- `measurement_boundary`
- `environment_summary`
- `n_observations`
- `status`
- `validation_errors`

Allowed terminal status values:

- `VERIFIED`
- `INCONCLUSIVE`

Phase 0 MUST NOT emit a causal `SUPPORTED` or `NOT_SUPPORTED` verdict.

## 9. Interpretation boundary

OBSERVED:

- exact timing values;
- timing API identity;
- timing boundary metadata;
- runner/environment metadata;
- workload identity.

VERIFIED:

- provenance contract passes;
- measurement boundary is explicitly evidenced;
- Frozen Core identity is preserved.

INFERRED:

- none in Phase 0.

UNKNOWN:

- causal explanation of G4 latency;
- whether an alternative measurement path would change the observation;
- whether environment differences cause the observed latency.

Therefore:

`MEASUREMENT_BOUNDARY_VERIFIED` must never be rewritten as `G4_ROOT_CAUSE_PROVEN`.

## 10. Frozen Core audit

The execution must verify the SHA-1 blob identity of:

`src/jamp/run.py`

Expected blob:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Any mismatch is a fail-closed condition.

## 11. State machine

Initial:

- EXP-22 Phase 0 = OPEN
- G4 Gate 1 = CONTRACT_VIOLATION
- G4 root cause = UNKNOWN
- Frozen Core = LOCKED

Terminal experiment states:

- VERIFIED
- INCONCLUSIVE

No transition is permitted from RUNNING directly to VERIFIED without terminal artifact validation.

## 12. Non-goals

This phase does not:

- change production behavior;
- change `src/jamp/run.py`;
- change the G4 threshold;
- run a causal intervention;
- clear G4;
- replace EXP-21 evidence;
- claim that measurement, scheduling, topology, GC, or environment is the cause.

## 13. Base identity

Contract created against:

- base branch: `main`
- base commit: `80c9d4b31f60c3552412c99e26579e2b4261656c`

The contract itself is research documentation only.
