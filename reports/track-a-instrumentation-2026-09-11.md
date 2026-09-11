# Track A instrumentation drift report

Date: 2026-09-11

## Binding metadata

- Anchor: `49a5c86be320cab5f998001182e6a3ffa836ec1c`
- Characterization tag: `track-a-instrumentation-v1`
- Tag SHA: `NOT AVAILABLE — tag is not present in the accessible GitHub ref namespace`
- Scope: this characterization applies to the identified immutable Track A tag only, not to Track A in general.
- Re-characterization required if the `closure()` invocation pattern, operator set, or roots change.

## Baseline

The experimental branch was created from `49a5c86be320cab5f998001182e6a3ffa836ec1c`.
The canonical Track A harness uses `track_a/experiment.py` and `track_a/common.py`.

The canonical runner was executed unchanged first (C). A second run used the same
logic with instrumentation enabled but all records written to `/dev/null` (N).
A third diagnostic mode kept the same records in memory (I).

## C == N invariant

**PASS.**

All 30 paired runs had identical full traces between C and N.

Matrix:

- roots: 2, 3, 5
- seeds: 0, 1, 2, 42, 99
- strategies: `BASELINE_RANDOM`, `TREATMENT_TARGETED`
- N: 200
- max_objects: 120
- total runs: 30

No evidence was found that the instrumentation changed RNG consumption,
selection order, or state evolution in the C/N comparison.

## Instrumentation fields

At the selection boundary the diagnostic records:

`step, strategy_name, n_candidates_total, n_candidates_novel, chosen_op, chosen_expr_repr, state_size`

The expression field uses `str(...)`; no expression hash is used for logging.
The existing `State.index` remains the value-based set used by the harness.
No `generate_candidates` or target substitution mechanism was changed semantically;
the instrumentation only exposes the candidate pool and selected result.

## Saturation point

For all 30 runs the first observation of `n_candidates_novel == 0` occurs at
state step **13**.

Therefore the specific early-saturation finding proposed in the diagnostic plan
(`k < 13` followed by continued execution to 13) is **not observed**.

The important observation is what happens at step 13: the state has saturated,
but the outer loop does not terminate on saturation. It continues calling the
selection routine until `N=200`, while `state_size` remains 13 and no new object
is added.

The run therefore ends as `MAX_ITERATIONS`, not because the generator still has
material, but because saturation is not an explicit stopping condition.

Across the 30 runs there were 5,808 post-saturation selection attempts recorded
after the first zero-novel observation. This is diagnostic evidence of repeated
selection attempts after saturation, not a new experimental mechanism.

## Steps 11–13

The successful additions at state steps 11–13 are not identical across seeds.
Their order varies, for example among the three expressions:

- `(d|(d*k_6))`
- `integer?(d*k_6)`
- `(d*(k_6^2))=(q^2)`
- `gcd((d*k_6),q,1)`

with the exact `d` determined by the root.

Thus the path is seed-dependent near the saturation boundary. This is not an
instrumentation artifact: C and N traces are identical.

After state step 13, repeated selection attempts return already-seen expressions
or no candidates; these repetitions do not change the state.

## Cross-seed final states

For each fixed root and strategy, the final state at step 13 is exactly equal
under canonicalized string-set comparison for seeds `0,1,2,42,99`.

Results:

| root | strategy | cross-seed final states |
|---|---|---|
| 2 | BASELINE_RANDOM | identical (5/5) |
| 2 | TREATMENT_TARGETED | identical (5/5) |
| 3 | BASELINE_RANDOM | identical (5/5) |
| 3 | TREATMENT_TARGETED | identical (5/5) |
| 5 | BASELINE_RANDOM | identical (5/5) |
| 5 | TREATMENT_TARGETED | identical (5/5) |

Every final state contains 13 expressions.

## Interpretation

The data support the following limited conclusion:

1. Instrumentation drift was not detected: **C == N** across all 30 runs.
2. Saturation occurs at the same state boundary, step 13, for every tested
   root, seed, and strategy.
3. Seeds change the **path/order** of successful additions, especially near
   steps 11–13, but do not change the final state in this Track A harness.
4. The harness has no saturation early-stop. Once step 13 is reached, it keeps
   attempting selection and terminates only when the iteration budget is
   exhausted.

This is an observation about the current Track A harness. It is not evidence
for a general JAMP property and is not a provenance claim.
