# ADR-001 — External Caller-Supplied Budget Contracts

- Status: PROPOSED
- Scope: EXP-19 research / architecture boundary
- Production/runtime change: none
- Frozen Core change: none

## 1. Context

EXP-19 measures physical performance characteristics of the JAMP graph path.
The measured R3 values are empirical observations. They do not, by themselves,
define an acceptable latency requirement.

JAMP is treated at this boundary as a verification kernel / library layer.
A kernel can measure and report execution characteristics without originating
the normative latency budget of the application, protocol, or deployment that
calls it.

The repository evidence does not identify an internal JAMP application service,
control loop, webhook consumer, dashboard, or other product owner that would
legitimately define an end-to-end latency SLA for the kernel.

## 2. Decision

JAMP MUST NOT originate a normative latency budget for an external use case.

When a latency budget is required, the budget MUST be supplied by the external
caller or domain contract and treated as an explicit research input.

The contract boundary is:

```
External caller / domain
    T_total_ms, w_proj, workload profile
                |
                v
          JAMP kernel
                |
                v
       empirical measurement
                |
                v
       evidence-backed routing
```

The domain inputs are:

1. `T_total_ms` — end-to-end latency budget supplied by the caller/domain.
2. `w_proj` — fraction of that budget allocated to the measured JAMP critical path.
3. Workload profile — the declared metric-binding context.
4. Any population or environment qualifier required by the caller/domain contract.

The derived target is:

```
B_target_ms = T_total_ms * w_proj
```

JAMP MUST NOT infer these values from its own benchmark measurements.

## 3. Decision semantics

`BLOCKED_BY_MISSING_BUDGET` means that the external caller/domain budget
contract required for the routing decision has not been supplied.

It does NOT mean that JAMP has a missing internal SLA.

A routing decision becomes evidence-backed only after the external inputs and
their provenance are available.

For an optimization experiment:

```
Metric(Baseline) > B_target(caller)
        => optimization is a justified research candidate
```

This is a routing condition, not an automatic requirement to optimize and not
a claim about universal JAMP performance.

## 4. Consequences

### Positive

- Empirical benchmark results remain separate from normative requirements.
- A synthetic project-wide SLA cannot be created from benchmark observations.
- Different callers can supply different legitimate budgets without changing
  the JAMP kernel contract.
- EXP-19 optimization work can be triggered by an actual external constraint
  rather than by an arbitrary threshold.

### Constraints

- EXP-19.R3-BUDGET cannot reach a terminal routing decision until the required
  external budget inputs are supplied.
- A caller/domain contract must identify the relevant workload and environment
  before a measured statistic can be interpreted against its budget.
- Benchmark measurements remain evidence, not service guarantees.

## 5. Scope boundary

This ADR does not:

- modify `src/jamp`;
- introduce a runtime SLA;
- introduce a benchmark threshold;
- accept or reject OPT-1;
- promote the R3 measurements (median 88.54 ms, P95 97.24 ms, max/peak
  99.24 ms) into requirements;
- define a particular external product, caller, or domain that has not been
  evidenced.

The R3 values remain empirical anchors only.

## 6. Relation to EXP-19

PR #86 (`EXP-19.R3-BUDGET`) remains the experiment-specific budget
specification. Its budget inputs are interpreted under this architectural
boundary: they are caller/domain inputs, not JAMP-originated requirements.

PR #89 (`EXP-19.MEM-OPT / OPT-1`) remains measurement-only. It introduces
no SLA or optimization threshold.

## 7. Frozen Core invariant

```
Delta(src/jamp) = 0
```

The ADR is a documentation-only architectural decision and does not alter the
Frozen Core.

## 8. Evidence discipline

The following distinctions remain mandatory:

- measured performance != SLA;
- benchmark peak != universal worst-case bound;
- missing external budget != defective kernel SLA;
- passing a benchmark != satisfying an unspecified domain contract;
- optimization candidate != approved optimization.

Any future domain budget must be provenance-linked to the caller/domain
artifact that establishes it before being used for EXP-19 routing.

## 9. Review / supersession

This ADR is PROPOSED until reviewed against the repository evidence and accepted
as the governing architecture decision for the EXP-19 budget boundary.

If later evidence identifies a different JAMP boundary with an internally owned
normative SLA, this ADR may be superseded by a new evidence-backed decision.
