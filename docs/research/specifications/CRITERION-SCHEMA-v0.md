# Criterion Schema v0

**Status:** Draft / Pre-Freeze  
**Layer:** N2 — Criterion  
**Governing contract:** `PROVENANCE-CONTRACT-v0`

## 1. Purpose

This document defines the Draft schema for the N2 Criterion object in the Normative Research Layer v0.

A Criterion is an atomic deterministic rule for evaluating an observation. It is bound to one hypothesis and prediction and contains its own evaluation logic and mandatory self-test controls. It does not define global specification semantics or aggregation across criteria.

This schema is subordinate to `PROVENANCE-CONTRACT-v0` and must not be interpreted as modifying that frozen contract.

## 2. Schema

```text
Criterion:
  criterion_id: UUIDv4 / Content-Namespace ID
  criterion_version: String (semantic version)
  hypothesis_ref: HashLink
  prediction_ref: HashLink
  preconditions: List[ConditionRule]
  observation_schema: SchemaDefinition
  acceptance_predicate: PureLogicExpression
  rejection_predicate: PureLogicExpression
  inconclusive_predicate: PureLogicExpression
  self_test_cases:
    pass_case: RawObservationSample
    fail_case: RawObservationSample
    inconclusive_case: RawObservationSample
  provenance_reference: HashLink
  criterion_hash: SHA-256
```

## 3. Field Semantics

### `criterion_id`

Immutable identity of the Criterion object or its content namespace.

### `criterion_version`

Version of the Criterion object. A frozen change creates a new Criterion version rather than modifying the existing frozen object.

### `hypothesis_ref`

Content-addressed reference to one exact immutable Hypothesis object.

### `prediction_ref`

Content-addressed reference to one exact immutable Prediction object.

### `preconditions`

Prerequisites required for deterministic evaluation of this Criterion. They are part of the frozen Criterion definition.

### `observation_schema`

Defines the shape and domain of raw observation data accepted by the Criterion predicates.

### `acceptance_predicate`

Pure deterministic logic evaluating an observation against the acceptance condition.

### `rejection_predicate`

Pure deterministic logic evaluating an observation against the rejection condition.

### `inconclusive_predicate`

Pure deterministic logic evaluating an observation against the inconclusive condition.

### `self_test_cases`

Mandatory deterministic control fixtures for the three result classes:

- `pass_case` MUST evaluate the acceptance predicate to `TRUE`;
- `fail_case` MUST evaluate the rejection predicate to `TRUE`;
- `inconclusive_case` MUST evaluate the inconclusive predicate to `TRUE`.

The self-tests validate logical executability and determinacy of the Criterion. They do not establish the empirical truth of the underlying hypothesis.

### `provenance_reference`

Content-addressed reference to the provenance record associated with creation/authoring of the Criterion.

### `criterion_hash`

SHA-256 computed from the canonical representation of all Criterion fields except `criterion_hash` itself.

## 4. N2 Logical Invariants

### I1 — Mutual Exclusivity

For every observation in the explicitly frozen `COVERED` domain, no more than one of the three predicates may evaluate to `TRUE`:

```text
PASS ∩ FAIL = ∅
PASS ∩ INCONCLUSIVE = ∅
FAIL ∩ INCONCLUSIVE = ∅
```

### I2 — Exhaustive Coverage

For every observation in the explicitly frozen `COVERED` domain, exactly one predicate must evaluate to `TRUE`:

```text
PASS ∪ FAIL ∪ INCONCLUSIVE = COVERED
```

An observation outside an explicitly frozen `COVERED` domain is not silently assigned a result. If such a boundary exists, it must itself be defined by the frozen Criterion/Specification context.

### I3 — Deterministic Evaluation

Given the same Criterion, preconditions, and observation, predicate evaluation MUST produce the same result. Evaluation errors, unresolved predicates, or nondeterministic outcomes are not valid classifications.

### I4 — Self-Test Completeness

All three mandatory self-test cases MUST exist and MUST evaluate to their designated result classes before the Criterion may be frozen.

### I5 — Self-Test Isolation

Self-test execution MUST use the frozen Criterion predicates and MUST NOT consume experimental Raw Evidence.

### I6 — Criterion Isolation

A Criterion MUST NOT define or modify the Specification, Criterion Set, Aggregation Rule, or other frozen research artifacts.

### I7 — No Post-Hoc Interpretation

A Criterion MUST be fully defined before the associated execution begins. Manual post-hoc interpretation cannot substitute for a missing or undefined predicate.

## 5. Contract Bindings

This schema supports all mandatory Criterion fields required by `PROVENANCE-CONTRACT-v0`:

- `criterion_id`
- `criterion_version`
- `hypothesis_ref`
- `prediction_ref`
- `preconditions`
- `observation_schema`
- `acceptance_predicate`
- `rejection_predicate`
- `inconclusive_predicate`
- `self_test.pass_case`
- `self_test.fail_case`
- `self_test.inconclusive_case`
- `provenance_reference`

Undefined predicates, `TBD`, or manual post-hoc interpretation are invalid Criterion definitions.

## 6. Non-Responsibilities

Criterion does not define:

- global research specification;
- Criterion Set membership or aggregation;
- experimental Raw Evidence;
- Classification records produced from experimental execution;
- Verdicts;
- empirical truth of the hypothesis.

## 7. Freeze Boundary

This document is **DRAFT / PRE-FREEZE**.

A frozen Criterion is immutable. Changes to its normative definition require a new Criterion version and corresponding content hash; historical frozen Criteria must not be rewritten.

## 8. Conformance

Subordinate to `PROVENANCE-CONTRACT-v0` and `NORMATIVE-LAYER-v0`. In any conflict, the frozen `PROVENANCE-CONTRACT-v0` governs.
