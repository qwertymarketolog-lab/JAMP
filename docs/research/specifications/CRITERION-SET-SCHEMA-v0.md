# Criterion Set Schema v0

**Status:** Draft / Pre-Freeze  
**Layer:** N3 — Criterion Set  
**Governing contract:** `PROVENANCE-CONTRACT-v0`

## 1. Purpose

This document defines the Draft schema for the N3 Criterion Set object in the Normative Research Layer v0.

A Criterion Set is the immutable container that binds one or more exact immutable Criteria to the immutable Aggregation Rule used by an execution. It defines the criterion collection and aggregation binding, but does not contain experimental evidence, classification results, or verdicts.

This schema is subordinate to `PROVENANCE-CONTRACT-v0` and must not be interpreted as modifying that frozen contract.

## 2. Schema

```text
CriterionSet:
  set_id: UUIDv4 / Content-Namespace ID (alias: criterion_set_id)
  version: String (semantic version)
  criteria: List[HashLink] (exact immutable Criterion hashes, len >= 1)
  aggregation_rule_ref: HashLink (immutable Aggregation Rule)
  provenance_reference: HashLink (optional authoring provenance reference)
  criterion_set_hash: SHA-256
```

`criterion_set_hash` is computed from the canonical representation of all Criterion Set fields except `criterion_set_hash` itself.

## 3. Field Semantics

### `set_id`

Immutable identity of the Criterion Set. `criterion_set_id` may be used as an implementation-level alias, but the normative contract field name is `set_id`.

### `version`

Version of the Criterion Set. A frozen change to the set creates a new version rather than modifying the existing frozen object.

### `criteria`

Non-empty collection of content-addressed HashLinks to exact immutable Criterion objects. References to `latest`, `current`, mutable tags, or other moving identifiers are not permitted.

### `aggregation_rule_ref`

Content-addressed HashLink to the exact immutable Aggregation Rule used to combine classifications. The aggregation rule is part of the identity of the Criterion Set.

### `provenance_reference`

Optional content-addressed reference to the authoring/provenance record for the Criterion Set. This is an additional schema field and does not replace any required contract field.

### `criterion_set_hash`

Deterministic SHA-256 identity of the canonical Criterion Set representation excluding the hash field itself. Any change to criteria, aggregation binding, version, or another hashed field must produce a different set hash.

## 4. N3 Invariants

### I1 — Non-Empty Set

`criteria` MUST contain at least one Criterion reference.

An empty Criterion Set is not a valid execution criterion set.

### I2 — Exact Immutable Criterion References

Every element of `criteria` MUST resolve to one exact immutable Criterion object identified by its content hash.

Moving references such as `latest`, `current`, branch-relative names, or mutable tags are not valid Criterion Set references.

### I3 — Exact Immutable Aggregation Reference

`aggregation_rule_ref` MUST resolve to one exact immutable Aggregation Rule.

The aggregation logic used by an execution MUST therefore be fixed before execution begins.

### I4 — Deterministic Set Identity

For the same canonical Criterion Set fields, `criterion_set_hash` MUST be identical.

Any change to the criteria collection, aggregation rule reference, version, or other hashed field MUST change the resulting hash.

### I5 — No Post-Execution Mutation

A frozen Criterion Set MUST NOT be modified after execution begins. A methodological or normative change requires a new Criterion Set version and a new set hash; historical artifacts remain unchanged.

### I6 — No Experimental Data

Criterion Set definition MUST NOT depend on Raw Evidence, Classification, or Verdict data produced after execution begins.

### I7 — No Verdict Logic in the Container

The Criterion Set binds criteria and the aggregation rule by reference. It does not contain empirical observations, classification outcomes, or a post-hoc verdict.

## 5. Contract Bindings

This schema preserves the exact required Criterion Set fields defined by `PROVENANCE-CONTRACT-v0`:

- `set_id`
- `version`
- `criteria`
- `aggregation_rule_ref`
- `criterion_set_hash`

The frozen contract states that any change to a criterion or the aggregation rule creates a new set hash. This schema additionally requires exact immutable references and a non-empty criterion collection as local N3 invariants.

## 6. Non-Responsibilities

Criterion Set does not define:

- individual Criterion predicate semantics;
- Raw Evidence;
- Classification records;
- Verdict results;
- post-execution interpretation;
- modification of the frozen Specification;
- modification of the frozen Aggregation Rule.

## 7. Freeze Boundary

This document is **DRAFT / PRE-FREEZE**.

A frozen Criterion Set is immutable. Changes to its normative definition or referenced criterion/aggregation composition require a new Criterion Set version and corresponding content hash; historical frozen sets must not be rewritten.

## 8. Conformance

Subordinate to `PROVENANCE-CONTRACT-v0` and `NORMATIVE-LAYER-v0`. In any conflict, the frozen `PROVENANCE-CONTRACT-v0` governs.
