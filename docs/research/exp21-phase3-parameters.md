# EXP-21 Phase 3 Quantitative Parameter Lock

## Status

- **Phase:** 3
- **State:** `QUANTITATIVE PRE-REGISTRATION LOCKED`
- **Branch:** `research/exp21-phase3-bounding-proposal`
- **Parent charter:** `034f02e6d8d7b96366c19cbdf847f5ba3a6ecbda`
- **Treatment execution:** `NOT_STARTED_AT_LOCK`
- **Production intervention:** `NOT_AUTHORIZED`
- **Frozen Core:** `LOCKED`

## 1. Tail Reduction Target

**Parameter:** `X = 50%`

The primary treatment criterion requires at least a 50% reduction in maximum observed edge inspections relative to the preregistered Phase 2 baseline.

With the Phase 2 maximum of 20,000 edge inspections, this corresponds to a treatment maximum of **10,000 or fewer** edge inspections.

`tail_reduction = 100 * (20,000 - treatment_max) / 20,000`

The criterion is satisfied only when `tail_reduction >= 50%`.

## 2. Median Non-Regression

**Parameter:** `epsilon = 0%`

The treatment p50 must not exceed the baseline p50.

With the Phase 2 baseline p50 of 102 edge inspections:

`p50_delta = 100 * (treatment_p50 - 102) / 102 <= 0%`

Any positive p50 regression fails the preregistered non-regression condition.

## 3. Decision Contract

Both quantitative conditions are mandatory:

1. `tail_reduction >= 50%`
2. `p50_delta <= 0%`

A treatment that improves the tail but violates the median invariant is **NOT_CONFIRMED**.

Missing or unverifiable measurements are **INCONCLUSIVE**, never PASS.

No threshold may be relaxed, increased, or redefined after treatment results are observed.

## 4. Baseline Lock

The quantitative reference is the Phase 2 diagnostic evidence already recorded:

- N = 100 start-node observations.
- p50 edge inspections = 102.
- maximum edge inspections = 20,000.
- canonical architectural anchor = node 0.

These values are reference evidence, not newly measured treatment data.

## 5. Anti-P-Hacking Boundary

The values `X = 50%` and `epsilon = 0%` are fixed before implementation or treatment benchmark execution.

Changing either threshold after treatment observations exist constitutes a protocol change and cannot be used to reinterpret those observations under this preregistration.

## 6. Frozen Core Guard

The Phase 3 proposal remains experimental and non-production:

`Delta(src/jamp) = 0`

No implementation, benchmark result, or threshold outcome authorizes modification of `src/jamp`.

## 7. Execution Boundary

Only after this parameter-lock commit may the Phase 3 comparative benchmark harness be implemented.

The benchmark must compare the preregistered Phase 2 baseline against treatment under the same workload identity, start-node population, measurement definition, and provenance requirements defined by the Phase 3 charter.

**Parameter lock is evidence of protocol fixation, not evidence that the hypothesis is confirmed.**
