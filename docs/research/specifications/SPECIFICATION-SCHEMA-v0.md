# Specification Schema v0

**Status:** Draft / Pre-Freeze
**Layer:** N1 — Specification
**Governing contract:** `PROVENANCE-CONTRACT-v0`

## 1. Purpose

This document defines the Draft schema for the N1 Specification object in the Normative Research Layer v0.

The Specification is the root pointer and protocol-metadata container for a research execution. It does not contain classification predicates or aggregation rules; those responsibilities belong to Criterion and Criterion Set respectively.

This schema is subordinate to `PROVENANCE-CONTRACT-v0` and must not be interpreted as modifying that frozen contract.

## 2. Schema

```text
Specification:
  spec_id: UUIDv4 / Content-Namespace ID
  spec_version: String (semantic version)
  hypothesis_ref: HashLink
  prediction_ref: HashLink
  criterion_set_ref: HashLink
  preconditions: List[ConditionRule]
  observation_schema: SchemaDefinition
  frozen_at: ISO8601 Timestamp | null (Draft only)
  spec_hash: SHA-256
```

## 3. Field Semantics

### `spec_id`

Immutable identity of the Specification object or its content namespace.

### `spec_version`

Version of the Specification schema/object. A frozen change creates a new version rather than modifying the existing frozen object.

### `hypothesis_ref`

Content-addressed reference to one exact immutable Hypothesis object.

### `prediction_ref`

Content-addressed reference to one exact immutable Prediction object.

### `criterion_set_ref`

Content-addressed reference to one exact immutable Criterion Set. The reference must identify the concrete immutable object; symbolic references such as `latest`, `current`, `main`, or equivalent aliases are prohibited.

### `preconditions`

Frozen protocol/state constraints applicable to the execution. They are data/conditions, not classification predicates.

### `observation_schema`

Frozen definition of the permitted raw-observation structure. It does not encode acceptance, rejection, or aggregation logic.

### `frozen_at`

`null` is permitted while the object remains Draft. When the Specification is frozen, this field must contain the concrete freeze timestamp required by `PROVENANCE-CONTRACT-v0`.

### `spec_hash`

SHA-256 computed from the canonical representation of all Specification fields except `spec_hash` itself. Any modification to a covered field produces a different content hash.

## 4. N1 Invariants

- **I1:** Specification contains no `acceptance_predicate`, `rejection_predicate`, or `inconclusive_predicate`.
- **I2:** Specification contains no aggregation rule or inline aggregation logic.
- **I3:** `hypothesis_ref`, `prediction_ref`, and `criterion_set_ref` resolve to exact immutable content-addressed objects.
- **I4:** Symbolic or moving references such as `latest`, `current`, or `main` are invalid.
- **I5:** `spec_hash` is deterministic and computed from a canonical representation excluding `spec_hash` itself.
- **I6:** A modification to a frozen Specification requires a new Specification version and immutable identity/hash.
- **I7:** `frozen_at = null` is permitted only before freezing; a frozen Specification must contain a concrete timestamp.
- **I8:** Specification fields must not contain verdict-bearing interpretation introduced after execution begins.

## 5. Conformance

The schema conforms to the frozen `PROVENANCE-CONTRACT-v0` requirements for Specification: identity, version, hypothesis/prediction/criterion-set references, freeze timestamp, and content hash.

The schema does not define Criterion predicates, Criterion Set aggregation, Classification, or Verdict semantics; those remain separate normative objects.

## 6. Freeze Status

This document is **DRAFT / PRE-FREEZE**.

It must undergo contradiction audit against `PROVENANCE-CONTRACT-v0` before it can be frozen as `SPECIFICATION-SCHEMA-v0`.
