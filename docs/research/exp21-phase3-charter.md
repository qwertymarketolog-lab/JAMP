# EXP-21 Phase 3 Bounding / Memoization Pre-Registration Charter

## Status

- **Phase:** 3
- **State:** `PRE-REGISTERED PROPOSAL`
- **Base lineage:** `research/exp21-multi-ai-federation-r0`
- **Production intervention:** `NOT_AUTHORIZED`
- **Frozen Core:** `LOCKED`

This document defines the research boundary before implementation or test-mock changes. It does not authorize a production algorithmic change.

## 1. Hypothesis

A bounded reachability lookup/cache intervention can reduce the worst-case tail inspection count for hub start nodes, including the canonical architectural anchor node `0`, relative to the Phase 2 baseline.

The primary effect metric is the reduction in worst-case edge inspections:

`tail_reduction = 100 * (baseline_tail - treatment_tail) / baseline_tail`

The minimum effect threshold `X%` is a preregistration parameter and must be fixed before any treatment implementation is evaluated. No post-hoc threshold may be chosen from observed treatment results.

## 2. Non-Regression Invariant

Typical start-node traversal must not regress beyond the preregistered tolerance `epsilon`:

`p50_delta = 100 * (treatment_p50 - baseline_p50) / baseline_p50 <= epsilon`

The value of `epsilon` must be fixed before treatment evaluation. A reduction in the hub tail cannot compensate for a violation of the non-regression invariant.

## 3. Baseline

The Phase 2 diagnostic baseline is the N=100 start-node dispersion sample recorded by PR #141 / artifact `10680173546`:

- p50 edge inspections: `102`
- maximum observed edge inspections: `20,000`

The canonical architectural anchor remains `CANONICAL_G4_FIXED_ANCHOR_NODE = 0`. It is structural and must not be selected from treatment telemetry.

## 4. Evidence Gate

Before any production-facing or core implementation change is considered, an isolated benchmark must compare:

1. Phase 2 baseline traversal.
2. Proposed bounded traversal and/or memoization treatment.

The benchmark must preserve the same workload definition, start-node population, measurement definition, and provenance fields needed to compare treatment with baseline.

Required measurements include:

- N of start-node observations.
- Edge-inspection count per observation.
- p50 edge inspections.
- p95 edge inspections.
- maximum edge inspections.
- canonical anchor node `0` result.
- treatment/baseline effect size.
- non-regression delta against `epsilon`.
- workload specification identity/hash.
- target commit SHA.

The benchmark must fail closed if required provenance or comparison fields are missing.

## 5. Intervention Boundary

The proposal may investigate:

- reachability lookup caching;
- memoization;
- an explicit exploration/bounding mechanism.

Any intervention must be isolated so that rollback to the Phase 2 baseline is unambiguous.

If `src/jamp` is ever modified, that modification requires a separate evidence gate and must be explicitly isolated behind an experimental feature flag or separate experimental module. This charter does not authorize such a modification.

## 6. Decision Contract

The Phase 3 treatment is eligible for further evaluation only if all preregistered conditions are satisfied:

- tail reduction is at least `X%`;
- p50 non-regression is within `epsilon`;
- required tail-envelope measurements are present;
- baseline and treatment workload identity is verified;
- Frozen Core boundaries are verified.

Failure of any required condition yields `NOT_CONFIRMED` for the proposed intervention. Missing evidence yields `INCONCLUSIVE`, not PASS.

No production optimization decision may be inferred from partial, synthetic, or post-hoc-selected evidence.

## 7. Explicit Non-Claims

This charter does not claim:

- that caching or bounding will improve G4 wall-clock latency;
- that topology is the sole cause of all G4 latency variance;
- that the proposed intervention is safe for production;
- that Phase 3 will authorize a change to `src/jamp`.

Those questions require independent evidence.

## 8. Frozen-Core Guard

The invariant remains:

`Delta(src/jamp) = 0`

unless a later, separately authorized evidence gate demonstrates a necessary core change. This proposal branch must not alter the Frozen Core merely to improve benchmark results or satisfy a threshold.

## 9. Pre-Registration Boundary

This charter is the research contract for Phase 3 proposal work. Any change to `X`, `epsilon`, workload identity, primary metric, or decision criteria after treatment results exist is a protocol change and must not be used to reinterpret those results.

Implementation and test-harness work begins only after the preregistered parameters are explicitly fixed.
