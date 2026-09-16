# Specification Gate v0

**Status:** Draft / Pre-Freeze  
**Layer:** N4 — Specification Gate  
**Governing contract:** `docs/research/PROVENANCE-CONTRACT-v0.md`  

## 1. Purpose

Specification Gate v0 is the pre-execution enforcement boundary for the normative research layer. It verifies that a Specification and its referenced Criterion Set are structurally complete, referentially coherent, self-testable, deterministic, and semantically covered before experimental execution is permitted.

The Gate does not evaluate whether a hypothesis is true. It evaluates whether the research protocol is sufficiently well-formed and verified to cross the execution boundary.

## 2. Architectural Boundary

The Gate is strictly pre-execution.

It MUST NOT consume, inspect, or derive any decision from experimental Raw Evidence or experimental results.

The Gate returns local gate states:

- `GATE_PASS`
- `GATE_FAIL`

These states are distinct from the canonical provenance-verifier states `PROVENANCE_VALID` and `PROVENANCE_INVALID` defined by `PROVENANCE-CONTRACT-v0`.

## 3. Operations

### 3.1 `validate_referential_integrity(spec_ref)`

Validates the complete reference chain required by the Specification. External immutable hash references MUST be resolvable and consistent with the referenced versions and hashes.

The operation does not replace the responsibilities of the Specification, Criterion, Criterion Set, or Aggregation Rule layers; it verifies their required cross-references at the Gate boundary.

### 3.2 `run_criterion_self_tests(criterion_set_ref)`

Executes the declared `pass_case`, `fail_case`, and `inconclusive_case` self-tests for every Criterion in the referenced Criterion Set through its predicates.

A Criterion Set cannot pass the Gate if any required self-test is missing, fails, is ambiguous, or produces a nondeterministic result.

### 3.3 `verify_predicate_coverage(criterion_set_ref)`

Verifies mutual exclusivity of PASS, FAIL, and INCONCLUSIVE predicates and complete coverage within the explicitly frozen `COVERED` domain.

The Gate MUST NOT invent, expand, or dynamically redefine the `COVERED` domain.

### 3.4 `evaluate_gate(spec_ref) -> GateResult`

The main Gate entry point. It performs all required structural, referential, self-test, semantic, coverage, determinism, and hash-consistency checks under fail-closed rules.

Any unresolved, missing, contradictory, nondeterministic, or failed required condition produces `GATE_FAIL` and blocks execution.

## 4. Required Gate Checks

The Gate checks, at minimum:

1. required Specification fields and versions;
2. immutable reference resolution and hash consistency;
3. Criterion Set existence and non-empty Criterion membership;
4. required Criterion predicates and self-tests;
5. Criterion predicate mutual exclusivity;
6. complete predicate coverage within `COVERED`;
7. deterministic evaluation of predicates and self-tests;
8. immutable Aggregation Rule reference;
9. absence of unresolved `TBD` or otherwise undefined required decision predicates;
10. freeze-boundary consistency.

The exact normative field requirements remain governed by `PROVENANCE-CONTRACT-v0` and the subordinate schemas.

## 5. Fail-Closed Rule

The Gate is fail-closed.

`GATE_PASS` is permitted only when every required Gate condition is satisfied.

Missing information, failed self-tests, predicate overlap, incomplete `COVERED` coverage, nondeterminism, unresolved references, hash/reference mismatch, or any unknown required state MUST prevent execution.

The Gate MUST NOT convert an unknown or unresolved condition into success.

## 6. Determinism Invariant

For the same immutable Specification, Criterion Set, Aggregation Rule, and referenced artifacts, repeated Gate evaluation MUST produce the same Gate result and equivalent deterministic diagnostic output.

## 7. Isolation Invariant

The Gate interface MUST NOT accept experimental observations, Raw Evidence, execution results, classifications, or verdicts as inputs to the Gate decision.

The Gate validates the protocol before the experiment; it does not validate the experiment after observing its outcome.

## 8. Self-Test Invariant

Every required Criterion self-test MUST execute before `GATE_PASS` can be returned.

A single missing or unsuccessful required self-test is sufficient for `GATE_FAIL`.

## 9. Non-Responsibilities

Specification Gate v0 does not:

- determine whether the hypothesis is true;
- inspect experimental Raw Evidence;
- classify experimental observations;
- aggregate experimental classifications into a verdict;
- modify the Specification, Criterion, Criterion Set, Aggregation Rule, or frozen research artifacts;
- repair invalid frozen artifacts in place.

Corrections to frozen artifacts require a new version under the freeze boundary.

## 10. Conformance

This Draft is subordinate to `PROVENANCE-CONTRACT-v0`. In case of conflict, the frozen contract governs.

The Gate's local `GATE_PASS` / `GATE_FAIL` vocabulary MUST NOT be interpreted as the canonical provenance-verifier states.

## 11. Freeze Boundary

This document is Draft / Pre-Freeze. No implementation is authorized by this document alone.

Once Specification Gate v0 is frozen, changes to its normative requirements require a new version rather than modification of the frozen artifact.
