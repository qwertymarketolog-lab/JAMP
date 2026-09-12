# Track A experiment.py reproduction — 2026-09-12

## Preregistration

Reproduction: Track A experiment.py @ d1b3a8c

Parameters: ROOTS=(2,3,5), SEEDS=(0,1,2,42,99), N=200, max_objects=120, strategies as in code.

Method: source artifacts fetched from GitHub API at the frozen anchor and executed in an isolated environment. The paired sweep semantics were reproduced directly from the fetched `common.py` and `experiment.py` source. No repository code or frozen anchor was modified for execution.

Expected: 30 runs total (3 roots × 5 seeds × 2 strategies).

Measure: solved, steps, final_size (`len(State.objects)`), plus the code's reported progress, AST depth and stop reason.

Comparison: no matching published 30-run result artifact was found by repository code search; therefore this report records the reproduction result without asserting a historical numerical match.

## Source identity

- Anchor: `d1b3a8c7e0cb6a16fb2eafacc5509382cecbcc39`
- `track_a/common.py` blob SHA: `d0956421f54e76a89f4a845e306f30f7b1d3c8e8`
- `track_a/experiment.py` blob SHA: `c6ca39e2ada1e5e74c124b2326cac17596ec5f12`
- `common.py` default `State.max_objects`: 120
- `experiment.py` defaults: ROOTS=(2,3,5), SEEDS=(0,1,2,42,99), N=200, max_objects=120

## Execution environment

- OS: Debian GNU/Linux 13 (trixie)
- Kernel: Linux 6.18.35
- Python: 3.13.5
- No package installation was required.
- The repository itself was not cloned because the execution container had no DNS access to GitHub. The frozen source blobs were retrieved through the connected GitHub API and run in isolation.

## Results

All 30 runs completed with the same terminal result:

- `solved = False`
- `steps = 13`
- `progress = 7`
- `final_size = 13`
- `ast_depth = 9`
- `stop_reason = MAX_ITERATIONS`

| root | seed | strategy | solved | steps | progress | final_size | ast_depth | stop_reason |
|---|---:|---|---|---:|---:|---:|---:|---|
| sqrt(2) | 0 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(2) | 0 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(2) | 1 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(2) | 1 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(2) | 2 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(2) | 2 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(2) | 42 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(2) | 42 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(2) | 99 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(2) | 99 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(3) | 0 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(3) | 0 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(3) | 1 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(3) | 1 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(3) | 2 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(3) | 2 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(3) | 42 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(3) | 42 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(3) | 99 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(3) | 99 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(5) | 0 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(5) | 0 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(5) | 1 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(5) | 1 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(5) | 2 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(5) | 2 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(5) | 42 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(5) | 42 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(5) | 99 | BASELINE_RANDOM | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |
| sqrt(5) | 99 | TREATMENT_TARGETED | false | 13 | 7 | 13 | 9 | MAX_ITERATIONS |

## Aggregate finding

30/30 runs reached exactly 13 objects and stopped by `MAX_ITERATIONS`; 0/30 were solved. Both strategy arms produced identical measured outcomes for every root and seed in this reproduction.

This is a reproduction of the frozen `experiment.py` parameterization, not the expanded R_test scan from Issue #39. The parameter gap remains a separate finding and is not resolved by this run.

The repeated `final_size = 13` is an empirical result of this 30-run reproduction. It does not by itself establish that 13 is an invariant or explain the origin of 13.

## Result artifact hash

SHA-256 of the local raw JSON result record: `6a498b4077913dc1196413aadc0fed47e66d78d491e0ebce947f9895c117ecb3`
