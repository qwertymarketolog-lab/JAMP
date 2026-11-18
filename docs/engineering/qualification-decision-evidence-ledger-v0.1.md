# Qualification Decision / Evidence Ledger Contract v0.1

Status: DESIGN-ONLY / PRE-IMPLEMENTATION

## 1. Purpose

Define the deterministic audit boundary between requirement evaluation and the
Evidence Ledger.

The contract records why a qualification decision was produced, which
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

The qualification result boundary is inherited exactly from PR #264/#265:

- `QUALIFIED` — every required requirement is satisfied by matching VERIFIED evidence.
- `INCONCLUSIVE` — required evidence/input is missing, malformed, unresolved,
  contradictory, or otherwise prevents deterministic qualification.

No additional qualification result status is introduced by this contract.

A requirement value mismatch is `INCONCLUSIVE`, consistent with PR #264/#265.
The audit record may retain a deterministic per-requirement evaluation outcome
such as `FAILED`, but that internal outcome MUST NOT become a third
qualification result status.

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
| ledger_snapshot_id | immutable logical ledger snapshot identity |
| ledger_snapshot_digest | digest of the selected ledger snapshot |
| checker_id | deterministic qualification checker |
| checker_version | exact checker version |
| checker_digest | checker source/content digest |
| decision_status | exactly QUALIFIED or INCONCLUSIVE |
| created_at | UTC creation timestamp |
| decision_digest | digest of canonical decision preimage |

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

Allowed internal evaluation statuses are:

- `SATISFIED`
- `FAILED`
- `INCONCLUSIVE`

`FAILED` is an internal audit outcome only. It MUST NOT be emitted as a
Qualification Decision status.

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

The evaluator MUST reject or return `INCONCLUSIVE` for:

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

## 8. Canonical decision-digest preimage

The `decision_digest` MUST be computed from a canonical UTF-8 JSON object
containing exactly these fields:

```
{
  "decision_contract_version": "...",
  "task_id": "...",
  "subject_id": "...",
  "requirement_set_hash": "...",
  "evidence_scope_hash": "...",
  "ledger_snapshot_id": "...",
  "ledger_snapshot_digest": "...",
  "checker_id": "...",
  "checker_version": "...",
  "checker_digest": "...",
  "decision_status": "...",
  "created_at": "..."
}
```

Canonicalization rules:

1. UTF-8 encoding.
2. JSON object keys sorted lexicographically.
3. No insignificant whitespace.
4. JSON strings use standard JSON encoding without application-level semantic normalization.
5. Arrays, where introduced by a future contract version, preserve declared
   order; v0.1 decision identity contains no arrays.
6. Numeric values are forbidden in the v0.1 decision identity object.
7. `decision_id` and `decision_digest` are excluded from the preimage to
   prevent circularity.
8. SHA-256 is computed over the canonical UTF-8 JSON bytes.
9. Any change to fields or canonicalization rules requires a new contract
   version.

`created_at` participates in decision identity; reproducing the same semantic
decision at another timestamp creates a distinct decision record.

## 9. Fail-closed rules

The evaluator MUST return `INCONCLUSIVE` when:

1. required evidence is missing;
2. evidence digest does not match;
3. evidence scope is ambiguous;
4. required provenance is unresolved;
5. requirement input is malformed;
6. checker input is incomplete;
7. checker version/digest is unresolved;
8. contradictory evidence prevents deterministic evaluation;
9. canonical decision-digest inputs are incomplete or invalid.

The evaluator MUST NOT introduce a separate `FAILED` qualification status.

No AI-generated confidence, ranking, heuristic, or narrative may override a
fail-closed result.

## 10. Audit record

Each completed evaluation MUST produce an append-only Decision Audit Record
containing:

- decision identity;
- requirement-set identity;
- evidence-scope identity;
- ledger snapshot identity;
- all requirement evaluation records;
- checker identity;
- terminal qualification result;
- decision digest;
- creation timestamp.

The audit record MUST be sufficient to reconstruct the decision without
contacting an external provider.

An audit record is evidence of the evaluation process and provenance chain; it
is not by itself proof that the underlying real-world claim is true.

## 11. Relationship to existing contracts

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

## 12. Non-goals

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

## 13. Frozen Core

`src/jamp/run.py` MUST remain unchanged.

Locked blob:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Required:

`Δ(src/jamp/run.py) = 0`

## 14. Freeze rule

This document is DESIGN-ONLY / PRE-IMPLEMENTATION.

Conformance requires a separate implementation and deterministic test-vector
contract. Any normative change to decision identity, evidence binding,
canonicalization, status semantics, or audit-record construction requires a
new contract version.
