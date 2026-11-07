# Qualification Decision / Evidence Ledger Contract v0.1

Status: SUPERSEDED / NON-NORMATIVE / HISTORICAL-DESIGN-ONLY

> **Disposition:** This document is retained as historical design material only. It is **not authoritative** for Qualification Decision terminal statuses in v0.1.
>
> The authoritative qualification boundary is defined by PR #264/#265 and consumed by:
> `docs/engineering/qualification-decision-evidence-ledger-v0.1.md`
>
> For v0.1, terminal qualification results remain exactly:
> - `QUALIFIED`
> - `INCONCLUSIVE`
>
> The `SUPPORTED`, `NOT_SUPPORTED`, and `BLOCKED` states below MUST NOT be interpreted or implemented as additional terminal qualification results. No change to PR #264/#265 semantics is implied.

## Purpose

Define the audit contract connecting a qualification decision to the evidence ledger without converting evidence into truth.

Boundary:

`Evidence records -> decision sufficiency evaluation -> qualification decision record -> audit trail`.

This contract records why a decision was or was not supportable within a declared scope. It does not assert that the underlying claim is universally true.

## Decision states

Historical/non-normative terminology retained below:

- `SUPPORTED`
- `NOT_SUPPORTED`
- `INCONCLUSIVE`
- `BLOCKED`

`VERIFIED` is not a qualification decision state.

A decision MUST include an explicit scope and decision rule.

## Required ledger linkage

Every qualification decision record MUST preserve:

- decision_id
- scope_id
- decision_state
- requirement_id
- evidence_record_ids
- evidence_statuses
- provenance references
- decision_rule_id/version
- evaluated_at
- evaluator identity/version
- unresolved_conditions, when applicable

Evidence references MUST remain traceable to their original ledger records.

## Sufficiency versus truth

The decision layer answers:

`Is the available evidence sufficient for this declared decision rule and scope?`

It MUST NOT silently transform this into:

`Is the underlying proposition universally true?`

A `SUPPORTED` decision therefore means only that the declared rule is satisfied by the declared evidence scope.

## Evidence-state barriers

The qualification layer MUST preserve source evidence states:

- `OBSERVED` remains `OBSERVED`;
- `UNKNOWN` remains `UNKNOWN`;
- `OFFLINE_FIXTURE` remains `OFFLINE_FIXTURE`;
- `REJECTED` evidence cannot satisfy a requirement;
- no evidence state may be upgraded to `VERIFIED` by qualification processing.

An evidence record with missing provenance is invalid and cannot be used to support a decision.

## Fail-closed decision matrix

| Evidence condition | Historical handling terminology |
|---|---|
| required evidence present and rule satisfied | SUPPORTED |
| required evidence present but rule contradicted | NOT_SUPPORTED |
| evidence insufficient or unresolved | INCONCLUSIVE |
| mandatory evidence/provenance missing or invalid | BLOCKED |
| rejected evidence only | BLOCKED |
| offline fixture used without a rule explicitly allowing fixture scope | BLOCKED |
| conflicting evidence without deterministic resolution | INCONCLUSIVE |

The matrix does not select a winner among conflicting evidence unless the decision rule explicitly defines a deterministic resolution procedure.

## Audit trail invariant

Every decision MUST be reconstructable from:

`decision_id -> scope_id -> requirement_id -> decision_rule_id/version -> evidence_record_ids -> provenance -> decision_state`.

The ledger MUST retain enough identity to reproduce the decision evaluation without rewriting raw evidence.

## Provenance preservation

Qualification processing MUST NOT replace:

- source identifiers with decision identifiers;
- fixture identifiers with product identifiers;
- source locators with derived URLs;
- original timestamps with evaluation timestamps;
- raw payload hashes with hashes of derived output.

Derived records MAY add decision metadata, but MUST retain references to original provenance.

## Example

A requirement asks whether a canonical attribute is supported within a declared offline fixture scope.

If #285 produces an `OBSERVED` RawObservation with deterministic source trace and the decision rule explicitly permits offline fixtures, the historical terminology below may describe the evidence as `SUPPORTED` for that scope, but the v0.1 terminal qualification result remains governed by #264/#265.

That does not establish live-source availability or universal semantic validity.

If the same observation is `UNKNOWN`, the qualification layer cannot promote it to `QUALIFIED`.

## Compatibility

Consumes:

- #281 fixture provenance contract;
- #283 parser test-vector semantics;
- #284 fixture -> RawObservation -> ledger provenance mapping;
- #285 ledger preservation vectors.

Preserves fail-closed semantics and does not redefine the WB raw schema.

## Non-goals

No runtime QualificationEngine, API, parser, evidence-ledger implementation, CI, credentials, schema expansion, or changes to #281/#283/#284/#285.

## Frozen Core

`src/jamp/run.py` remains locked at blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

Expected: `Δ(src/jamp/run.py) = 0`.
