# Architecture

JAMP is layered around a strict separation between causal state, evaluation, search, policy adaptation and experimental orchestration.

## Current architectural layers

1. **Causal core** — immutable causal events, deterministic ordering, integrity and replay.
2. **Evaluation** — stateless evaluation over readonly state and causal history.
3. **Pattern index** — cross-session evidence indexing with digest isolation.
4. **Policy adaptation** — deterministic policy updates with exploration floor and immutable configuration.
5. **Search boundary** — policy-guided candidate generation without retroactive mutation of history.
6. **Experiment registry** — reproducible experiment artifacts and task-family identity.
7. **Task isolation** — family ownership and zero-transfer default.
8. **Controlled transfer** — explicitly authorized cross-task projections with provenance and integrity checks.
9. **Ablation** — experimental removal of guardrails to distinguish correlation/regression from causal necessity.

## P19 → P20.7 specification

The onboarding-level architecture map, milestone contracts, gate semantics, and extension boundary are maintained in [`p19-p20.7.md`](p19-p20.7.md).

## Boundary rule

Lower layers do not silently depend on higher-level search or policy decisions. Experimental orchestration may consume lower-layer evidence, but it must preserve the contracts of the causal and integrity layers.

The architecture is research-facing first: reproducibility and auditability are part of the mechanism, not documentation added after the fact.
