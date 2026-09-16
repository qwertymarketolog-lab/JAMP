# Provenance Contract v0

**Status:** FROZEN
**Version:** v0
**Purpose:** Define the minimum provenance, integrity, and derivability contract for an auditable JAMP research cycle.

## 1. Scope

This contract governs the chain from a frozen research specification to a reproducible verdict:

`SPECIFICATION → CRITERIA → EXECUTION → RAW EVIDENCE → CLASSIFICATION → VERDICT`

The contract guarantees integrity of referenced artifacts, deterministic derivability of classification and verdict from frozen rules and recorded evidence, and fail-closed provenance verification. It does **not** establish the empirical truth of the underlying hypothesis.

## 2. Canonical Objects

### 2.1 Specification

A frozen description of the research question, hypothesis, prediction, applicable criteria, and protocol.

Required fields:

- `spec_id`
- `spec_version`
- `hypothesis_ref`
- `prediction_ref`
- `criterion_set_ref`
- `spec_hash`
- `frozen_at`

Once frozen, a change creates a new specification version. A frozen specification is immutable.

### 2.2 Criterion

A deterministic rule for evaluating an observation.

Required fields:

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

Undefined predicates, `TBD`, or manual post-hoc interpretation are not valid criterion definitions.

### 2.3 Criterion Set

The immutable set of criteria and the aggregation rule used by an execution.

Required fields:

- `set_id`
- `version`
- `criteria`
- `aggregation_rule_ref`
- `criterion_set_hash`

Any change to a criterion or the aggregation rule creates a new set hash.

### 2.4 Execution

A concrete execution bound to exact frozen inputs and implementation references.

Required fields:

- `execution_id`
- `spec_hash`
- `criterion_set_hash`
- `implementation_ref`
- `environment_ref`
- execution timestamps

`implementation_ref` must identify a concrete version; symbolic references such as `latest` or `current main` are insufficient.

### 2.5 Raw Evidence

The unclassified observations produced by an execution.

Required fields:

- `execution_id`
- `observation_schema`
- `observations`
- `evidence_hash`

Raw evidence is data, not interpretation. It must not contain verdict-bearing labels such as `PASS`, `FAIL`, `DETECTED`, `SUCCESS`, or equivalent semantic classifications as sources of truth.

### 2.6 Classification

The deterministic application of frozen criteria to raw evidence.

Each applicable observation/criterion pair must have exactly one classification from the frozen result domain.

The classification record must preserve:

- observation reference;
- criterion reference;
- predicate evaluation;
- resulting classification;
- `evidence_hash`;
- `criterion_set_hash`;
- `classification_hash`.

### 2.7 Verdict

The deterministic aggregation of the frozen classification vector under the frozen aggregation rule.

Required fields:

- `classification_hash`
- `aggregation_rule_hash`
- derived result
- `verdict_hash`

A verdict is not authoritative merely because it is recorded. It must be reproducible by the verifier.

## 3. Hash and Reference Chain

The following equalities must hold:

```text
Execution.spec_hash == frozen Specification.spec_hash
Execution.criterion_set_hash == frozen CriterionSet.criterion_set_hash
Classification.evidence_hash == RawEvidence.evidence_hash
Classification.criterion_set_hash == CriterionSet.criterion_set_hash
Verdict.classification_hash == Classification.classification_hash
Verdict.aggregation_rule_hash == frozen AggregationRule.hash
```

Hashes establish artifact identity/integrity. They do not, by themselves, establish logical correctness.

## 4. Integrity

Integrity is satisfied only when every recorded hash/reference resolves to the exact frozen artifact it claims to reference.

A hash mismatch, unresolved reference, version mismatch, or implementation mismatch is a provenance failure.

## 5. Derivability

Classification must satisfy:

```text
CLASSIFICATION = Evaluate(FROZEN CRITERIA, RAW EVIDENCE)
```

Verdict must satisfy:

```text
VERDICT = Aggregate(CLASSIFICATION, FROZEN AGGREGATION RULE)
```

Both operations must be deterministic under the contract. A recorded classification or verdict that differs from recomputation is invalid.

## 6. Predicate Requirements

For every applicable observation, acceptance, rejection, and inconclusive predicates must be mutually exclusive:

```text
PASS ∩ FAIL = ∅
PASS ∩ INCONCLUSIVE = ∅
FAIL ∩ INCONCLUSIVE = ∅
```

The predicates must provide complete coverage of the intended covered observation domain:

```text
PASS ∪ FAIL ∪ INCONCLUSIVE = COVERED
```

If a specification intentionally defines a domain outside `COVERED`, that boundary must itself be frozen and explicit. An undefined case is not silently classified.

## 7. Specification Self-Test

Every criterion must provide deterministic control fixtures for known acceptance, rejection, and inconclusive outcomes.

The Specification Gate must execute these controls before an experiment is permitted to run. Failure, ambiguity, nondeterminism, or inability to evaluate any control blocks execution.

## 8. Fail-Closed Rules

The provenance verifier must return `PROVENANCE_INVALID` for any of the following:

- missing specification;
- missing criterion or predicate;
- missing self-test;
- missing raw evidence;
- missing classification;
- missing aggregation rule;
- hash mismatch;
- unresolved or inconsistent reference;
- version mismatch;
- implementation identity mismatch;
- predicate evaluation error;
- nondeterministic predicate evaluation;
- overlapping classification predicates;
- incomplete required coverage;
- classification mismatch on recomputation;
- aggregation mismatch;
- verdict mismatch;
- unknown state that cannot be deterministically classified under the frozen contract.

`UNKNOWN` is not an implicit `PASS`, `FAIL`, or `INCONCLUSIVE`. Unresolved unknown state is invalid provenance.

## 9. Provenance Verifier Contract

An independent verifier must:

1. load the frozen Specification;
2. verify `spec_hash`;
3. load and verify the frozen Criterion Set;
4. verify Execution references;
5. verify Raw Evidence integrity;
6. re-evaluate frozen predicates against Raw Evidence;
7. reconstruct Classification;
8. compare the reconstructed classification with the recorded Classification;
9. load and verify the frozen Aggregation Rule;
10. recompute the Verdict;
11. compare the recomputed Verdict with the recorded Verdict;
12. emit either `PROVENANCE_VALID` or `PROVENANCE_INVALID` with machine-readable error codes.

The verifier must not modify the research artifacts during verification.

## 10. Post-Execution Information Boundary

No information introduced after execution begins may influence verdict derivation unless that information was already represented in the frozen Specification, Criterion Set, or Aggregation Rule.

A methodological correction discovered after execution requires a new specification/version and a new execution; it must not rewrite the historical result.

## 11. Separation of Evidence and Interpretation

Raw Evidence must remain separate from Classification and Verdict. Classification is the first layer at which frozen interpretation rules are applied.

Human-readable explanations may accompany a verdict, but explanatory prose is not an authoritative source of the verdict. The authoritative result is the deterministically recomputed result under the frozen contract.

## 12. Verification Result

The canonical verification states are:

- `PROVENANCE_VALID` — integrity and derivability checks pass.
- `PROVENANCE_INVALID` — at least one mandatory contract condition fails.

`PROVENANCE_VALID` means that the recorded result is internally reproducible under the frozen contract. It does not mean that the underlying hypothesis is empirically true.

## 13. Historical Experiments

This contract does not retroactively modify historical experiments. In particular, EXP-08 v1 remains an immutable historical experiment with its existing frozen specification, raw execution, classification, and methodological-gap record.

Future experiments may use this contract as their provenance standard. EXP-08 v2, if created, must be a new independently frozen experiment.

## 14. Design Invariant

The central invariant of Provenance Contract v0 is:

> No verdict-defining information may be introduced after execution begins unless it was already encoded in the frozen specification, criterion set, or aggregation rule.

And, for a recorded result:

> Integrity plus deterministic derivability is required for `PROVENANCE_VALID`.

---

**Freeze boundary:** This document is the normative v0 contract. Changes to its requirements constitute a new contract version rather than an edit to v0.
