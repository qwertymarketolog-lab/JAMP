# EXP-19.R3-BUDGET — Domain Budget Specification

Status: DRAFT / BUDGET PENDING

## 1. Purpose

This document separates the empirical performance observation from the domain latency
contract.

EXP-19.R3 produced a measured baseline for the G-scale benchmark. Those measurements
are evidence, not a normative SLA. No measured value is promoted into a requirement
without an externally supplied domain budget.

Production/runtime boundary: `src/jamp` remains unchanged. This specification is a
research/documentation artifact only.

## 2. Empirical anchor

Protocol: `R3-v0`

Reported R3 anchor:
- median: 88.54 ms
- P95: 97.24 ms
- max/peak: 99.24 ms

These values are treated as measured anchors from the R3 evidence. They do not, by
themselves, establish an acceptable latency target.

Terminal decision before domain budget is supplied:

`BLOCKED_BY_MISSING_BUDGET`

## 3. Domain Derivation Chain

The domain budget MUST be derived in this order:

### 3.1 End-to-End SLA

Define the total allowed latency for the complete user scenario or batch pipeline:

`T_total_ms > 0`

Example only (non-normative): `T_total_ms = 200 ms`.

The example MUST NOT be interpreted as the JAMP contract.

### 3.2 Critical-path allocation

Define the fraction of the end-to-end budget allocated to the EXP-19 graph projection
and its directly coupled graph operations:

`0 < w_proj <= 1`

Then:

`B_target_ms = T_total_ms * w_proj`

Example only:

`200 ms * 0.50 = 100 ms`

This allocation belongs to the domain/application contract, not to the benchmark.

### 3.3 Metric binding

Select the statistic according to the declared workload profile:

| Workload profile | Binding statistic | Rationale |
|---|---|---|
| Stable background / batch | Median | Represents central tendency |
| Interactive / SLO with tail control | P95 | Controls the high-latency tail |
| Hard real-time / safety-critical | Max/peak | No observed sample may exceed the bound |

The chosen statistic MUST be declared before interpreting the branch result.

## 4. Decision matrix

The R3 anchor is compared with the domain-derived `B_target_ms`.

### Median binding

| Condition | Branch |
|---|---|
| `B_target_ms >= 90 ms` | `EXP-19.R4` |
| `B_target_ms < 90 ms` | `EXP-19.R3-opt` |

Measured anchor: 88.54 ms.

### P95 binding

| Condition | Branch |
|---|---|
| `B_target_ms >= 100 ms` | `EXP-19.R4` |
| `B_target_ms < 100 ms` | `EXP-19.R3-opt` |

Measured anchor: 97.24 ms.

### Max/peak binding

The max/peak anchor is retained for hard real-time analysis:

`99.24 ms`

A max-bound decision requires an explicitly supplied hard upper budget. No such
budget is assumed by this document.

## 5. Decision semantics

The branch decision is a research-routing decision, not a claim that the system is
universally fast or slow.

- If the domain budget is sufficiently above the observed anchor according to the
  selected metric, proceed to `EXP-19.R4` for the next experimental stage.
- If the domain budget is below the observed anchor, proceed to
  `EXP-19.R3-opt` to investigate optimization.
- If `T_total_ms`, `w_proj`, or the required statistic is missing, the terminal
  decision remains `BLOCKED_BY_MISSING_BUDGET`.

## 6. Required domain inputs

Before this specification can produce a terminal routing decision, the domain owner
must provide:

1. `T_total_ms` — end-to-end latency budget.
2. `w_proj` — allocated fraction for the EXP-19 critical path.
3. Workload profile — batch, interactive/SLO, or hard real-time/safety-critical.
4. Any population/environment qualifier that makes the SLA conditional
   (for example, deployment class or runner class).

The specification MUST NOT infer these values from the R3 measurements.

## 7. Evidence discipline

The following distinctions are mandatory:

- measured performance != SLA;
- benchmark peak != universal worst-case bound;
- confidence != support for a normative requirement;
- passing a benchmark != satisfying an unspecified domain contract;
- a provisional numerical example != a project-wide performance target.

The R3 benchmark remains an empirical observation until a domain budget is supplied
and provenance-linked to the decision.

## 8. Core delta

Target:

`Delta(src/jamp) = 0`

This artifact introduces no production/runtime behavior and no performance threshold
inside the JAMP core.

## 9. Next transition

Once the domain inputs in Section 6 are supplied, instantiate:

`B_target_ms = T_total_ms * w_proj`

Then bind the declared statistic to the corresponding R3 anchor and record the
resulting branch as a new evidence-backed research decision.

Until then:

`EXP-19.R3 = VERIFIED / MEASURED`

`Terminal Decision = BLOCKED_BY_MISSING_BUDGET`
