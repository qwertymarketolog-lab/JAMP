# Control Examples v0

**Status:** Draft / Pre-Freeze  
**Layer:** N5 — Control Examples  
**Governing contract:** `PROVENANCE-CONTRACT-v0`  
**Purpose:** specification-level control vectors for the Specification Gate

## 1. Scope

This document defines deterministic, abstract control examples for the pre-execution Specification Gate. The examples are normative test vectors for future implementation tests; they are not experimental observations and do not contain Raw Evidence, execution results, classifications, or canonical research verdicts.

## 2. Control Example Model

Each example defines:

- `example_id` — stable identifier;
- `purpose` — isolated condition being demonstrated;
- `input_artifacts` — abstract Specification/Criterion Set references and their relevant fields;
- `intentional_condition` — the single condition intentionally varied;
- `expected_gate_status` — `GATE_PASS` or `GATE_FAIL`;
- `expected_diagnostic_code` — deterministic API diagnostic;
- `expected_invariants` — conditions that must remain satisfied.

The examples are specification-level vectors. They do not prescribe implementation details.

## 3. CE-01 — Happy Path

**Purpose:** demonstrate a structurally valid specification and criterion set that satisfy all pre-execution gate requirements.

**Input artifacts:**

- valid immutable Specification reference;
- valid immutable Criterion Set reference;
- non-empty criteria set;
- resolvable Aggregation Rule reference;
- complete predicate definitions;
- mutually exclusive PASS/FAIL/INCONCLUSIVE predicates;
- complete coverage of the explicitly frozen `COVERED` domain;
- complete, isolated self-test cases;
- deterministic evaluation.

**Intentional condition:** none; all required conditions are valid.

**Expected gate status:** `GATE_PASS`

**Expected diagnostic code:** none.

**Expected invariants:**

- no Raw Evidence is inspected;
- no execution result is inspected;
- no classification or verdict is produced;
- all required references and hashes are valid;
- all self-tests pass;
- predicate coverage is valid;
- evaluation is deterministic.

## 4. CE-02 — Hash Mismatch

**Purpose:** demonstrate fail-closed rejection when an immutable artifact reference does not match its declared hash.

**Input artifacts:**

- otherwise valid Specification and Criterion Set;
- one intentionally incorrect declared artifact hash.

**Intentional condition:** exactly one hash/reference integrity condition is invalid.

**Expected gate status:** `GATE_FAIL`

**Expected diagnostic code:** `HASH_MISMATCH`

**Expected invariants:**

- no Raw Evidence is inspected;
- no experimental result is consumed;
- no repair or mutation of the artifact is attempted;
- failure is deterministic;
- no downstream verdict is generated.

## 5. CE-03 — Predicate Overlap

**Purpose:** demonstrate fail-closed rejection when classification predicates overlap within the explicitly frozen `COVERED` domain.

**Input artifacts:**

- otherwise valid Specification and Criterion Set;
- two predicates intentionally constructed so that at least one covered input satisfies both.

**Intentional condition:** exactly one predicate exclusivity invariant is violated.

**Expected gate status:** `GATE_FAIL`

**Expected diagnostic code:** `PREDICATE_OVERLAP`

**Expected invariants:**

- the `COVERED` domain is not expanded or redefined by the Gate;
- no Raw Evidence is inspected;
- no execution result is consumed;
- no classification or verdict is generated;
- failure is deterministic.

## 6. CE-04 — Self-Test Failure

**Purpose:** demonstrate fail-closed rejection when a required criterion self-test does not satisfy its declared expected outcome.

**Input artifacts:**

- otherwise valid Specification and Criterion Set;
- one criterion whose required self-test case intentionally evaluates to a result different from its declared expected classification.

**Intentional condition:** exactly one required self-test fails.

**Expected gate status:** `GATE_FAIL`

**Expected diagnostic code:** `SELF_TEST_FAILURE`

**Expected invariants:**

- all other structural and reference conditions remain valid;
- no Raw Evidence is inspected;
- no experimental result is consumed;
- no repair or mutation is attempted;
- failure is deterministic;
- no downstream classification or verdict is generated.

## 7. Isolation Rule

Each control example MUST isolate one intentional failure condition. A future implementation test MUST establish that unrelated gate conditions remain valid so that the expected diagnostic is attributable to the declared condition.

CE-01 is the sole positive control. CE-02 through CE-04 are negative controls.

## 8. Provenance and Information Boundary

Control Examples are pre-execution specification artifacts. They MUST NOT contain:

- Raw Evidence;
- execution outputs;
- empirical observations;
- post-execution classifications;
- research verdicts;
- post-hoc acceptance thresholds derived from experimental data.

The Specification Gate MUST treat these examples as structural control inputs only.

## 9. Expected State Vector

| Example | Condition | Expected state | Diagnostic |
|---|---|---|---|
| CE-01 | All requirements satisfied | `GATE_PASS` | none |
| CE-02 | Hash/reference integrity violation | `GATE_FAIL` | `HASH_MISMATCH` |
| CE-03 | Predicate overlap | `GATE_FAIL` | `PREDICATE_OVERLAP` |
| CE-04 | Self-test failure | `GATE_FAIL` | `SELF_TEST_FAILURE` |

## 10. Conformance

This document is subordinate to `PROVENANCE-CONTRACT-v0`, `NORMATIVE-LAYER-v0`, the Specification Schema v0, Criterion Schema v0, Criterion Set Schema v0, Specification Gate v0, and Specification Gate API Contract v0. Where requirements conflict, the higher-level frozen contract governs.

This document does not freeze the contract and does not authorize implementation by itself. Changes after eventual freeze require a new version.
