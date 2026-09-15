# EXP-05 — Implementation Gate Notes

This note records implementation checks against the frozen EXP-05 protocol and scenarios. It does not modify the scientific criteria.

## Mandatory corrections before implementation

1. The frozen PRNG vector is `x_(n+1) = (1103515245*x_n + 12345) mod 2^31` with `u_n = x_n / 2^31`. The implementation must use that exact normalization; division by `2^31 - 1` is not equivalent to the frozen scenario.
2. The frozen Run Core returns `RunResult(state, steps, iterations, stop_reason)`, so adapter tests must inspect `result.state`, not `result.final_state`.
3. The Run Core structural contract requires `initial()`, `candidates()`, `admissible()`, `apply()`, `terminal()`, `strategy()`, and `budget`. The adapter must implement the existing contract without changing `src/jamp/run.py`.
4. Provenance events must expose `state_before`, `intended_action`, `actual_outcome`, `is_deviated`, and `state_after`. Position-only fields are insufficient to satisfy the frozen provenance requirement.
5. EXP-05A must assert that at least one deviation exists. A boolean type check alone does not test that criterion.
6. EXP-05B requires exact replay determinism independently for seed 1 and seed 2. Cross-seed trajectory divergence is observational only and must not be made a pass/fail condition.
7. No artifact-hash criterion is added by this note. EXP-05's frozen criteria concern execution and provenance; artifact-v0 neutrality was established separately in Q3b and is not silently redefined here.

The frozen documents remain authoritative: `EXP-05-SPEC.md` and `EXP-05-SCENARIOS.md`.
