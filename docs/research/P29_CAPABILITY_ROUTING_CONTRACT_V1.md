# P29 Capability-Based Task Routing Engine v0.1

## Status
Contract baseline for P29 v0.1.

## Purpose
Route a task only when repository-committed, task-scoped capability evidence establishes that a model satisfies every required capability.

P29 is a routing boundary, not a model-quality or global-qualification system.

## Contract

`CapabilityRouter.route_task(task_spec: TaskSpec) -> RoutingDecision`

### TaskSpec
- `task_type: str` — one of the task profiles declared by the evidence matrix.
- `required_confidence: str` — v0.1 accepts only `VERIFIED`.
- `max_latency: int | float | None` — optional latency bound in milliseconds.

### RoutingDecision
- `status: EXECUTE | REFUSE`
- `selected_model: str | None`
- `evidence_trace: dict`

## Evidence source

Canonical source:
`artifacts/research/jamp_task_scoped_derived_matrix_v2.json`

The router requires:
- schema `jamp-task-scoped-derived-matrix-v2`;
- 17/17 models and 170/170 checks;
- Frozen Core blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`;
- routing rule: every required capability must be `VERIFIED`.

The matrix evidence anchor is preserved in every decision trace.

## Decision rule

For task profile T with required capabilities R:

`EXECUTE` iff:
1. T is known;
2. `required_confidence == VERIFIED`;
3. no latency bound is requested unless latency evidence exists;
4. at least one model has `raw_status == VERIFIED` for every capability in R.

Otherwise return `REFUSE`.

v0.1 has no latency evidence in the committed capability matrix. Therefore a supplied `max_latency` is fail-closed to `REFUSE: LATENCY_EVIDENCE_UNAVAILABLE`.

## Selection

Selection is deterministic: eligible model IDs are sorted lexicographically and the first model is selected.

No model ranking, aggregate score, historical fallback, or synthetic evidence is allowed.

## Evidence semantics

- `VERIFIED` is the only status eligible for routing.
- `CONTRADICTED` and `INCONCLUSIVE` block routing.
- Missing capability evidence blocks routing.
- Routing does not upgrade evidence and does not imply correctness.
- Scope remains task-profile + model + capability evidence.

## Safety boundaries

- `src/jamp/run.py` is Frozen Core; required delta = 0.
- P29 v0.1 does not alter the Runtime `/v1/execute` fast path.
- No external model call is performed by the router.
- No credentials are read or persisted.
