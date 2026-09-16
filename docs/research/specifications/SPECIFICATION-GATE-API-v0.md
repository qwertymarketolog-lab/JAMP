# Specification Gate API Contract v0

**Status:** Draft / Pre-Freeze  
**Layer:** API Contract for N4 — Specification Gate  
**Governing contract:** `docs/research/PROVENANCE-CONTRACT-v0.md`  
**Normative parent:** `docs/research/specifications/SPECIFICATION-GATE-v0.md`  

## 1. Purpose

This document defines the abstract interface contract for the N4 Specification Gate. It specifies inputs, outputs, operation boundaries, deterministic diagnostics, and error classes without defining implementation code.

The API is deliberately pre-execution and provides no interface through which experimental Raw Evidence, execution results, classifications, or verdicts can influence Gate evaluation.

## 2. Design Principles

1. **Fail-closed:** unresolved or invalid required state cannot produce `GATE_PASS`.
2. **Pre-execution isolation:** Gate operations do not accept experimental data.
3. **Immutability:** referenced artifacts are identified by immutable hashes/versions.
4. **Determinism:** identical immutable inputs produce identical results and canonical diagnostics.
5. **Provenance separation:** local Gate states are distinct from canonical provenance-verifier states.
6. **No implementation commitment:** this contract defines behavior and data shapes, not programming-language classes or functions.

## 3. Input Types

### 3.1 `SpecificationRef`

An immutable reference identifying the Specification to validate.

Required properties:

- `spec_id`
- `spec_version`
- `spec_hash`

The reference MUST resolve to the exact immutable Specification identified by these fields.

### 3.2 `CriterionSetRef`

An immutable reference identifying the Criterion Set required by the Specification.

Required properties:

- `set_id`
- `version`
- `criterion_set_hash`

The Criterion Set reference MUST agree with the Specification's `criterion_set_ref`.

## 4. Operation: `validate_specification(spec_ref)`

### Input

`SpecificationRef`

### Output

`SpecificationValidationResult`

Conceptual fields:

- `status`: `VALID | INVALID`
- `spec_ref`
- `diagnostics`: ordered deterministic list of validation diagnostics
- `validated_hashes`: ordered immutable artifact/hash references

### Responsibilities

The operation verifies Specification-level structural conformance, required fields, immutable references, version/hash consistency, and conformance to the subordinate schema.

It MUST NOT inspect experimental Raw Evidence or any execution outcome.

## 5. Operation: `validate_referential_integrity(spec_ref)`

### Input

`SpecificationRef`

### Output

`ReferenceIntegrityResult`

Conceptual fields:

- `status`: `VALID | INVALID`
- `diagnostics`
- `resolved_refs`

The operation validates the complete required reference chain without assuming responsibilities belonging to the referenced lower-level artifacts.

## 6. Operation: `run_criterion_self_tests(criterion_set_ref)`

### Input

`CriterionSetRef`

### Output

`CriterionSelfTestResult`

Conceptual fields:

- `status`: `PASS | FAIL`
- `criterion_results`
- `diagnostics`

For every Criterion, the required `pass_case`, `fail_case`, and `inconclusive_case` MUST be evaluated through the declared predicates.

Any missing, failed, ambiguous, or nondeterministic required self-test causes `FAIL`.

## 7. Operation: `verify_predicate_coverage(criterion_set_ref)`

### Input

`CriterionSetRef`

### Output

`PredicateCoverageResult`

Conceptual fields:

- `status`: `VALID | INVALID`
- `covered_domain_ref`
- `overlap_diagnostics`
- `coverage_diagnostics`

The operation verifies mutual exclusivity and complete coverage strictly within the already-defined `COVERED` domain. It MUST NOT construct, infer, expand, or dynamically redefine that domain.

## 8. Operation: `run_gate(spec_ref)`

### Input

`SpecificationRef`

### Output

`GateResult`

Conceptual fields:

- `status`: `GATE_PASS | GATE_FAIL`
- `spec_ref`
- `validated_hashes`
- `diagnostics`
- `gate_contract_version`

### Required behavior

`run_gate()` invokes the required pre-execution validation operations and applies the fail-closed rule.

`run_gate()` MUST NOT accept parameters for:

- Raw Evidence;
- observations;
- execution results;
- classifications;
- verdicts.

A `GATE_PASS` is possible only when every required Gate condition is satisfied.

## 9. Diagnostic Contract

Diagnostics MUST be deterministic for identical immutable inputs.

Each diagnostic should identify, at minimum:

- stable error code;
- affected artifact/reference;
- failed invariant or contract requirement;
- deterministic human-readable description.

Diagnostics are explanatory outputs. They MUST NOT introduce post-execution facts or alter the normative decision rules.

## 10. Error Taxonomy

The API recognizes the following conceptual error classes:

- `MISSING_REQUIRED_FIELD`
- `SCHEMA_VIOLATION`
- `UNRESOLVED_REFERENCE`
- `HASH_MISMATCH`
- `VERSION_MISMATCH`
- `EMPTY_CRITERION_SET`
- `MISSING_PREDICATE`
- `MISSING_SELF_TEST`
- `SELF_TEST_FAILURE`
- `SELF_TEST_AMBIGUITY`
- `NONDETERMINISTIC_EVALUATION`
- `PREDICATE_OVERLAP`
- `INCOMPLETE_COVERAGE`
- `UNRESOLVED_STATE`
- `FREEZE_BOUNDARY_VIOLATION`

An implementation MAY represent these errors differently, but the semantic distinctions MUST remain preserved.

## 11. Determinism Contract

For identical immutable Specification, Criterion Set, Aggregation Rule, and referenced artifacts:

`run_gate(input) == run_gate(input)`

with identical Gate status and equivalent canonical diagnostic representation.

The API MUST NOT depend on runtime observations, wall-clock execution results, mutable global state, or experimental data when determining the Gate result.

## 12. Provenance Separation

`GATE_PASS` and `GATE_FAIL` are local pre-execution Gate states.

They MUST NOT be interpreted as `PROVENANCE_VALID` or `PROVENANCE_INVALID`.

Canonical provenance verification remains the responsibility of the independent verifier defined by `PROVENANCE-CONTRACT-v0`.

## 13. Non-Responsibilities

This API does not:

- determine hypothesis truth;
- inspect or classify experimental evidence;
- calculate an experimental verdict;
- replace the independent provenance verifier;
- modify referenced artifacts;
- repair frozen artifacts in place.

## 14. Freeze Boundary

This document is Draft / Pre-Freeze. It defines an interface contract only and authorizes no implementation.

After freezing, normative changes require a new API contract version rather than modification of the frozen artifact.

## 15. Conformance

This API Contract is subordinate to `PROVENANCE-CONTRACT-v0`, the N4 Specification Gate contract, and the N1–N3 subordinate schemas. In case of conflict, the higher-level frozen contract governs.
