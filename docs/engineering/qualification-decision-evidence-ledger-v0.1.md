# Qualification Decision / Evidence Ledger Contract v0.1

Status: DESIGN-ONLY / PRE-IMPLEMENTATION

## 1. Purpose

Define the deterministic audit boundary between requirement evaluation and the
Evidence Ledger.

The contract records **why a qualification decision was produced**, which
requirements were evaluated, which evidence records were used, and which
deterministic checker/contract versions governed the evaluation.

This contract does not execute qualification, acquire evidence, call AI/API
providers, or modify the Evidence Ledger implementation.

Boundary:

```
Requirement Set
      +
Evidence Ledger snapshot
      +
Deterministic checker
      |
      v
Requirement Evaluation
      |
      v
Qualification Decision
      |
      v
Decision Audit Record
```

## 2. Decision semantics

A Qualification Decision is a deterministic interpretation of a frozen
requirement set over a declared evidence scope.

Allowed terminal decision statuses:

- `QUALIFIED` — every required requirement evaluated successfully.
- `NOT_QUALIFIED` — at least one required requirement evaluated as failed.
- `INCONCLUSIVE` — a required input/evidence item is missing, malformed,
  contradictory, or otherwise unresolved.
- `FAILED` — the deterministic qualification procedure itself failed.

`INCONCLUSIVE` MUST NOT be converted to `QUALIFIED` by absence of errors,
AI opinion, catalog metadata, or current/live replacement evidence.

A qualification decision is a decision about the frozen evaluation scope; it
is not a general claim of real-world truth.

## 3. Required decision identity

Every decision MUST declare:

| Field | Requirement |
|---|---|
| decision_id | globally unique immutable identifier |
| decision_contract_version | exact contract version |
| task_id | qualification task identity |
| subject_id | product/entity being qualified |
| requirement_set_hash | exact frozen requirement set |
| evidence_scope_hash | deterministic identity of selected evidence |
| checker_id | deterministic qualification checker |
| checker_version | exact checker version |
| checker_digest | checker source/content digest |
| decision_status | terminal status |
| created_at | UTC creation timestamp |
| decision_digest | digest of canonical decision record |

The decision identity MUST be reproducible from a canonical preimage.

## 4. Requirement evaluation record

Each requirement evaluation MUST contain:

- `requirement_id`;
- `requirement_version`;
- `required` boolean;
- `evaluation_status`;
- canonical requirement input digest;
- referenced evidence IDs;
- referenced evidence digests;
- deterministic checker outcome/error code;
- normalized observed value(s), where applicable;
- expected predicate/constraint identity;
- evaluation record digest.

Allowed evaluation statuses:

- `SATISFIED`
- `FAILED`
- `INCONCLUSIVE`

A requirement MUST NOT be marked `SATISFIED` when a required evidence input
is absent or unresolved.

The model/AI output may be referenced as an observation, but MUST NOT be the
qualification oracle.

## 5. Evidence Ledger binding

The decision MUST reference an immutable logical snapshot of the Evidence
Ledger.

Required binding:

```
ledger_snapshot_id
ledger_snapshot_digest
evidence_ids[]
evidence_digests[]
```

Every referenced evidence record MUST resolve to the exact record used by the
evaluation.

The evaluator MUST reject:

- unknown evidence IDs;
- digest mismatch;
- evidence outside the declared scope;
- mutation of referenced evidence after decision creation;
- substitution of newer evidence without a new decision.

The Evidence Ledger remains append-oriented. A new evidence record does not
silently rewrite an existing decision.

## 6. Provenance chain

Minimum audit chain:

```
requirement_set_hash
        |
        v
evidence_scope_hash
        |
        v
ledger_snapshot_digest
        |
        +--> evidence_id -> evidence_digest
        |
        v
checker_id/version/digest
        |
        v
requirement_evaluation_digest[]
        |
        v
decision_digest
```

For CI-backed evidence, existing provenance fields such as commit SHA,
workflow, run ID, job ID, artifact ID, raw hash, and scope remain facts of the
evidence record. This contract does not redefine their semantics.

Missing provenance required by the selected requirement MUST result in
`INCONCLUSIVE`, not inferred success.

## 7. Deterministic evaluation

Given identical:

- requirement set bytes;
- evidence ledger snapshot;
- evidence contents/digests;
- checker version and digest;
- canonicalization rules;

the evaluator MUST produce identical requirement evaluations and decision
status.

The evaluator MUST be side-effect free with respect to qualification state.

No network/API/provider call is permitted during deterministic evaluation.

## 8. Fail-closed rules

The evaluator MUST return `INCONCLUSIVE` when:

1. required evidence is missing;
2. evidence digest does not match;
3. evidence scope is ambiguous;
4. required provenance is unresolved;
5. requirement input is malformed;
6. checker input is incomplete;
7. checker version/digest is unresolved;
8. contradictory evidence prevents deterministic evaluation.

The evaluator MUST return `FAILED` only for an actual deterministic procedure
failure, not merely for missing evidence.

No AI-generated confidence, ranking, heuristic, or narrative may override a
fail-closed result.

## 9. Audit record

Each completed evaluation MUST produce an append-only Decision Audit Record
containing:

- decision identity;
- requirement-set identity;
- evidence-scope identity;
- ledger snapshot identity;
- all requirement evaluation records;
- checker identity;
- terminal decision status;
- decision digest;
- creation timestamp.

The audit record MUST be sufficient to reconstruct the decision without
contacting an external provider.

An audit record is evidence of the evaluation process and provenance chain; it
is not by itself proof that the underlying real-world claim is true.

## 10. Relationship to existing contracts

This contract is additive and consumes existing semantics from:

- AEW v0.1 EvidenceRecord / EvidenceLedger;
- Evidence Acquisition Contract v0;
- deterministic qualification requirement contract v0.1.1;
- deterministic requirement test-vector contract v0.1.1;
- EvidencePolicy as the existing evidence-status boundary.

It does not redefine:

- EvidenceStatus;
- EvidenceRecord provenance fields;
- requirement semantics;
- normalization semantics;
- EvidencePolicy promotion;
- Frozen Core behavior.

The contract provides the missing audit-trail binding between those layers.

## 11. Non-goals

This contract does not implement:

- qualification runtime;
- marketplace parser runtime;
- AI provider/API calls;
- evidence acquisition;
- Evidence Ledger storage changes;
- CI workflow changes;
- test-suite changes;
- threshold changes;
- `src/jamp/run.py` changes.

## 12. Frozen Core

`src/jamp/run.py` MUST remain unchanged.

Locked blob:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Required:

`Δ(src/jamp/run.py) = 0`

## 13. Freeze rule

This document is DESIGN-ONLY / PRE-IMPLEMENTATION.

Conformance requires a separate implementation and deterministic test-vector
contract. Any normative change to decision identity, evidence binding,
canonicalization, status semantics, or audit-record construction requires a
new contract version.
