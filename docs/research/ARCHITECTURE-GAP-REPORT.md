# JAMP Architecture Gap Report

**Status:** AUDIT ARTIFACT

**Audit target:** `PROVENANCE-CONTRACT-v0`

**Frozen contract blob SHA-1:** `a63c3db9a8b0bdfe474e2ee573130e61055d1a2d`

**Purpose:** Record the architectural gap between the existing JAMP research/provenance infrastructure and the normative research layer defined by `PROVENANCE-CONTRACT-v0`.

## 1. Scope

This document records the result of an architecture audit. It does **not** modify, reinterpret, or replace the frozen `PROVENANCE-CONTRACT-v0`.

The audit distinguishes five statuses:

- **IMPLEMENTED** — the requirement is fulfilled by an identifiable and verifiable mechanism.
- **PARTIAL** — part of the requirement exists, but not as the complete contract-level object or invariant.
- **MISSING** — no corresponding contract-level mechanism was identified.
- **CONTRADICTED** — existing behavior directly violates the contract requirement.
- **UNVERIFIED** — a mechanism may exist, but the available evidence is insufficient to establish compliance.

The audit is an architectural assessment, not a claim about the truth of any research hypothesis.

## 2. Architectural split

The audit identifies two distinct layers.

### 2.1 Existing lower layer

JAMP already contains a substantial content-addressed integrity and provenance infrastructure spanning the research lifecycle:

`QUESTION → PLAN → EXECUTION → RESULT → INTERPRETATION → CONSENSUS → CLAIM → REVISION`

Relevant mechanisms include immutable/hash-bound research objects, evidence integrity, deterministic derivation, execution identity, recursive runtime lineage, interpretation provenance, deterministic consensus, and deterministic claim synthesis.

This layer predates the normative contract described below.

### 2.2 Missing normative upper layer

`PROVENANCE-CONTRACT-v0` defines an additional research-control layer:

`HYPOTHESIS → PREDICTION → SPECIFICATION → CRITERION SET → SPECIFICATION GATE → FROZEN BOUNDARY → EXECUTION → RAW EVIDENCE → CLASSIFICATION → AGGREGATION RULE → VERDICT → INDEPENDENT VERIFIER`

The audit did not identify this upper layer as a complete, universal set of frozen contract objects in the current architecture.

## 3. Compliance matrix

| Contract area | Status | Audit finding |
|---|---|---|
| Content-addressed research artifacts | IMPLEMENTED | Existing research objects are immutable/hash-bound and verified locally. |
| Evidence integrity | IMPLEMENTED | Evidence objects and verification mechanisms establish content integrity. |
| Evidence provenance | IMPLEMENTED | Evidence participates in explicit upstream/downstream provenance relationships. |
| Deterministic derivation | IMPLEMENTED | Derivation is represented as content-addressed, reproducible research state. |
| Hypothesis provenance | IMPLEMENTED | Hypothesis formation and upstream references are represented in the existing research model. |
| Question provenance | IMPLEMENTED | Questions are explicitly linked through the existing research chain. |
| Execution identity | IMPLEMENTED | Execution records are hash-bound to existing upstream research objects. |
| Raw observation boundary | IMPLEMENTED | Existing execution/evidence layers distinguish observations from later interpretation and claims. |
| Recursive runtime lineage | IMPLEMENTED | Runtime state records and verifies artifact lineage through the existing lifecycle. |
| Interpretation provenance | IMPLEMENTED | Interpretations are immutable/hash-bound and linked to result, execution, question, plan, trace and state. |
| Deterministic consensus | IMPLEMENTED | Consensus resolution is deterministic and conflict-aware. |
| Deterministic claim synthesis | IMPLEMENTED | Claims are derived from verified interpretations and carry provenance. |
| Frozen Specification object | MISSING | No universal contract-level Specification object with the required frozen identity was identified. |
| `spec_hash` execution binding | MISSING | Existing execution binding does not implement the v0 requirement as a universal specification reference. |
| Criterion object | MISSING | No universal Criterion object with acceptance/rejection/inconclusive predicates and self-test cases was identified. |
| Criterion Set | MISSING | No contract-level immutable criterion-set object with `criterion_set_hash` was identified. |
| Specification Gate | MISSING | No universal pre-execution gate enforcing structural and semantic specification validity was identified. |
| Predicate coverage / disjointness | MISSING | The v0 predicate coverage invariants are not implemented as a universal gate. |
| Criterion self-test | MISSING | Existing tests do not constitute the contract-defined criterion self-test layer. |
| Raw Evidence v0 object | PARTIAL | Raw observations exist, but not yet as the complete universal v0 Raw Evidence object. |
| Classification v0 | PARTIAL | Deterministic status/evaluation mechanisms exist locally, but not as the universal v0 classification object and chain. |
| Frozen aggregation rule | PARTIAL | Deterministic synthesis/consensus mechanisms exist, but the v0 frozen aggregation-rule object is not implemented as specified. |
| Verdict object | MISSING | No universal v0 Verdict object was identified. |
| `verdict_hash` | MISSING | No complete v0 verdict hash chain was identified. |
| Independent full-chain verifier | MISSING | Existing verification is distributed across local objects; a complete independent v0 verifier was not identified. |
| Integrity recomputation | IMPLEMENTED | Existing hash verification provides strong local integrity checks. |
| Full v0 derivability recomputation | MISSING | The complete Specification → Criterion Set → Evidence → Classification → Aggregation → Verdict derivation chain is not implemented. |

## 4. Contradiction finding

No `CONTRADICTED` requirement was established by this audit.

The absence of contradictions is significant: the existing architecture does not need to be characterized as broken or invalid merely because it does not implement a later normative contract. The identified gap is primarily one of **missing contract-level objects and gates**, not incompatible lower-level behavior.

## 5. Interpretation of the gap

The existing architecture should therefore be treated as a predecessor infrastructure layer rather than as an implementation failure.

Its strengths include:

- content addressing;
- immutable research artifacts;
- integrity verification;
- explicit provenance links;
- deterministic derivation;
- execution identity;
- recursive runtime lineage;
- interpretation provenance;
- deterministic consensus and claim synthesis.

The missing layer is normative. It must determine, **before execution**, what counts as an admissible specification, what criteria will be applied, how PASS/FAIL/INCONCLUSIVE are defined, how coverage is established, and how the final verdict is derived.

## 6. Frozen-boundary requirement

The architectural gap confirms the need for a hard boundary:

`SPECIFICATION → CRITERION SET → SPECIFICATION GATE → FROZEN`

followed by execution against the frozen contract.

Once frozen, post-execution observations must not retroactively alter the criteria, predicates, aggregation rule, or verdict semantics.

A discovered methodological defect after execution must therefore produce a new specification revision rather than a modification of the historical frozen specification.

## 7. EXP-08 preservation boundary

`EXP-08 v1` remains an independent historical research artifact.

Its frozen specification, raw execution, classification, methodological-gap note, and provenance history are not modified by this architecture audit.

In particular, the absence of mutation-specific PASS/FAIL criteria in the frozen EXP-08 v1 specification remains a methodological finding. It must not be repaired retrospectively by changing the historical experiment.

The future normative layer may be tested against a new specification revision or a new experiment derived from the preserved historical case.

## 8. Implementation boundary for the next phase

This report intentionally does not prescribe implementation details beyond the contract boundary.

The next architectural phase should address, as separate normative objects:

1. `Specification`;
2. `Criterion`;
3. `Criterion Set`;
4. `Specification Gate`;
5. frozen execution binding;
6. universal `Raw Evidence` representation;
7. universal `Classification` representation;
8. frozen aggregation rule;
9. `Verdict` object;
10. independent full-chain verifier.

Each object should be designed against the frozen contract before implementation begins.

## 9. Architectural conclusion

The audit establishes the following boundary:

> **JAMP does not currently violate PROVENANCE-CONTRACT-v0; the existing architecture predates the contract and does not yet implement its normative upper layer.**

Therefore:

- the existing lower integrity/provenance infrastructure is preserved;
- no contradiction with the frozen contract was established;
- the normative upper layer remains an architectural gap;
- EXP-08 v1 remains historically immutable;
- the next implementation phase has a clean, explicit starting boundary.

This report is an audit artifact and does not modify the frozen contract.
