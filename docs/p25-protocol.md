# P25 — Discovery and Generalization Protocol

**Status:** SPECIFIED
**Branch:** `research/p25-discovery-generalization`
**Baseline:** `main` at merge commit `4e6f6202cf643af3e607f451f198080aea954c89`

## 1. Purpose

P25 moves JAMP from infrastructure validation to an empirical test of whether a fixed domain operator set transfers from one member of a mathematical task family to another without operator modification.

This protocol is explicitly **not** a claim of discovery. Experimental observations must remain separate from interpretation and claim formation.

## 2. Research Question — P25.1

> Can a fixed set of algebraic operators, integrated as a JAMP domain executor, demonstrate measurable transfer from the √2 irrationality proof to the √3 irrationality proof without operator modification?

## 3. Hypothesis — P25.2

> H1: The operator set exhibits ≥50% success rate on √3 with equal initial weights, indicating task-family generalization within the "irrationality of √p" class.

The threshold is a pre-registered hypothesis criterion, not an expected or guaranteed outcome.

## 4. Blindness and anti-circularity constraints

1. The transfer target (√3) must not be encoded as a special-case route in the operator set.
2. The evaluator must not select or rewrite trajectories because they approach a known proof.
3. The experiment must not modify operators between √2 baseline and √3 transfer.
4. Raw execution output is evidence, not a claim.
5. A successful run does not by itself establish mathematical novelty or general discovery.
6. Any later claim must identify the exact experimental conditions and observed result.

## 5. Component isolation

JAMP remains the meta/research layer. The mathematical proof engine is a domain executor/plugin.

Required boundary:

```text
JAMP research layer
  Question → Hypothesis → Plan → Execution → Evidence → Claim
                         │
                         ▼
              domain executor interface
                         │
                         ▼
                 algebraic operator engine
```

The current post-merge `main` contains the JAMP research/execution boundary but does **not** contain the previously described v1.3.0 proof-solver operator engine. Therefore P25 execution cannot legitimately begin until the domain executor is supplied or independently imported as a declared experimental dependency.

## 6. Experimental plan — P25.3

| Experiment | Parameters | Criterion |
|---|---|---|
| Baseline (√2) | 20 seeds, N=200, equal weights | Success rate ≥70% only as replication criterion |
| Transfer (√3) | 20 seeds, N=200, equal weights; target axiom 2→3 only | Success rate ≥50% |
| Ablation: no target substitution | 20 seeds; exclude `op_substitute_into_target` | Record observed success rate; no assumed value |
| Ablation: frozen weights | 20 seeds; `learning_mode='none'` | Compare empirically with active mode |

The criteria above are fixed before execution. They must not be altered after observing results.

## 7. Required execution record — P25.4

Each run must produce a JAMP `ExecutionRecord` containing, at minimum:

- `question_hash`
- `plan_hash`
- deterministic `parameters`
- raw `observations`
- `execution_hash`
- `result_hash`
- `trace_hash` where the domain executor provides a trace
- `state_hash` where applicable
- upstream provenance binding

The existing JAMP execution contract rejects runtime metadata and separates raw observations from interpretation/claims.

## 8. Telemetry

Each trajectory must expose enough immutable telemetry to classify observed states as:

- `PROGRESS`
- `STAGNATION`
- `FAILURE`
- `SUCCESS` when the domain executor has an independently checkable success condition

State labels are observations of execution state. They are not claims about generalization.

## 9. Evidence — P25.5

The evidence package must contain:

- `success_rate`
- `avg_steps` among successful runs
- operator coverage
- seed-by-seed results
- stagnation/failure patterns
- complete parameter set
- trace/state hashes
- artifact SHA-256
- workflow/run identifier when executed in CI

Controls and ablations must be retained alongside experimental results.

## 10. Claim boundary — P25.6

A possible final claim may have the form:

> The operator set `{O₁...O₁₂}` generalized from √2 to √3 with observed Success Rate X% (baseline Y%), under the declared conditions. Under the target-substitution ablation, the observed Success Rate was Z%.

The claim must be populated only after execution and independent verification. No numerical result is asserted by this specification.

## 11. Current implementation gate

**P25.4 is BLOCKED pending domain-executor availability.**

The repository audit found JAMP's research modules and execution boundary, but no v1.3.0 algebraic operator engine, `Expr/Number/Symbol/Op` system, or √2 proof-search benchmark in the post-merge repository.

Therefore this protocol deliberately does **not** create a fake `domain_plugin_sqrt2.py` that pretends to execute a missing solver. Creating such an adapter would violate the blind-test and evidence-first requirements.

Next legitimate implementation step:

1. Identify and freeze the exact v1.3.0 domain-engine source as an external experimental dependency or restore it as a declared domain plugin.
2. Verify its operator set and target handling without modifying it for P25.
3. Implement the adapter against the real engine interface.
4. Run P25 baseline before transfer.
