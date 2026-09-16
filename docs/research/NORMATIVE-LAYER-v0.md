# Normative Research Layer v0

**Status:** Draft / Pre-Freeze Architecture Map

## 1. Status / Scope

This document defines the strict boundary, responsibilities, and structural hierarchy of the Normative Research Layer (NRL) v0 within JAMP.

It derives its authority from, and remains strictly subordinate to, `PROVENANCE-CONTRACT-v0`. It does not override or modify the frozen base contract.

## 2. Normative Layer Position

The Normative Research Layer sits upstream of execution and provenance infrastructure. It establishes whether a research protocol is formally valid before an experiment is permitted to run.

## 3. N1 — Specification

**Role:** Root pointer and metadata container for a research execution.

**Content:** `spec_id`, `spec_version`, `hypothesis_ref`, `prediction_ref`, `criterion_set_ref`, preconditions, and `observation_schema`.

**Restriction:** Specification contains no classification predicates or aggregation rules. Those responsibilities belong to Criterion and Criterion Set respectively.

## 4. N2 — Criterion

**Role:** Atomic evaluation unit.

**Content:** Identifier, version, hypothesis/prediction references, preconditions, expected observation schema, `acceptance_predicate`, `rejection_predicate`, `inconclusive_predicate`, and mandatory self-test cases.

**Constraint:** Predicates must be mutually exclusive and provide complete coverage of the intended covered observation domain. Undefined or untestable criteria fail closed.

## 5. N3 — Criterion Set

**Role:** Immutable container bundling one or more atomic criteria and the aggregation rule used by an execution.

**Content:** Criteria, `aggregation_rule_ref`, and `criterion_set_hash`.

**Constraint:** The aggregation rule must be fully defined and fixed before execution.

## 6. N4 — Specification Gate

**Role:** Fail-closed enforcement mechanism for formal protocol validity.

**Content:** Structural validation, referential validation, semantic validation, predicate coverage/exclusivity validation, self-test execution, and aggregation-rule validation.

**Core Rule:** Specification Gate MUST NOT consume, inspect, or derive any decision from experimental Raw Evidence.

The Gate does not evaluate whether the underlying hypothesis is empirically true. It returns only protocol-readiness status such as `GATE_PASS` or `GATE_FAIL`.

## 7. Responsibility Matrix

| Component | Governs Structure | Governs Logic / Predicates | Governs Aggregation | Evaluates Experimental Data |
|---|---|---|---|---|
| N1 Specification | Yes | No | No | No |
| N2 Criterion | No | Yes | No | No |
| N3 Criterion Set | Yes | No | Yes | No |
| N4 Gate | Yes (validation) | Yes (validation) | Yes (validation) | No |

## 8. Forbidden Cross-Boundary Dependencies

- **F1:** Specification components MUST NOT embed inline classification logic or custom predicates.
- **F2:** Criterion MUST NOT modify the Specification, Criterion Set, Aggregation Rule, or frozen research artifacts.
- **F3:** Specification Gate MUST NOT execute or authorize execution if any required validation, schema check, or self-test fails.
- **F4:** Specification Gate MUST NOT inspect experimental outcomes, raw observations, or intermediate analysis during its evaluation cycle.

## 9. Freeze Boundary

After the Specification and Criterion Set have been frozen, any modification requires a new version.

A changed normative object must not silently replace the frozen object referenced by an existing execution. New versions must receive new immutable identities/hashes as required by `PROVENANCE-CONTRACT-v0`.

## 10. Conformance Relation to PROVENANCE-CONTRACT-v0

This Normative Research Layer is subordinate to and intended to implement the specification and pre-execution verification requirements of `PROVENANCE-CONTRACT-v0`.

In the event of ambiguity or conflict, `PROVENANCE-CONTRACT-v0` remains the governing immutable standard. This document must not be interpreted as introducing a conflicting requirement into the frozen contract.

## 11. Key Invariants

- **I1:** Specification contains references and protocol parameters, but no classification logic.
- **I2:** Criterion contains atomic predicates and self-tests.
- **I3:** Criterion Set contains criteria and an aggregation-rule reference.
- **I4:** Gate checks only formal protocol readiness.
- **I5:** Gate does not read experimental Raw Evidence.
- **I6:** Gate does not evaluate the truth value of the hypothesis.
- **I7:** `GATE_FAIL` blocks progression to execution.
- **I8:** Gate validation is a pre-execution condition; it is not a substitute for experimental execution or verdict derivation.
- **I9:** Modifying a frozen normative object requires a new version.
- **I10:** No layer may implicitly acquire the responsibilities of another layer.

## 12. Freeze Status

This document is **DRAFT / PRE-FREEZE**. It becomes normative only after contradiction audit against the frozen `PROVENANCE-CONTRACT-v0` establishes:

```text
CONTRADICTED = 0
PARTIAL = 0
UNSPECIFIED = 0
```

Only then may this document be frozen as `NORMATIVE-LAYER-v0`.
