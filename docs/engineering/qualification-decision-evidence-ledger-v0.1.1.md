# Qualification Decision / Evidence Ledger Contract v0.1.1

## Purpose

Design-only contract linking deterministic requirement evaluation to an auditable decision ledger without implementing runtime qualification or evidence storage.

## Decision ledger record

Each qualification evaluation MUST produce a deterministic ledger record containing:
- `decision_id`: stable unique identifier;
- `evaluation_id`: identifier of the evaluation instance;
- `requirement_set_id`: identifier of the requirement set;
- `verdict`: `QUALIFIED` or `INCONCLUSIVE`;
- `criteria_results`: deterministic result for each evaluated requirement;
- `evidence_refs`: references to Claims/observations supporting each criterion;
- `reason_codes`: deterministic reasons for unsatisfied or unresolved criteria;
- `created_at`: evaluation timestamp;
- `contract_version`: ledger contract version.

## Evidence ledger invariants

1. Every criterion result MUST be traceable to its requirement and evidence references.
2. Every `QUALIFIED` decision MUST reference VERIFIED evidence for every required criterion.
3. `INCONCLUSIVE` MUST identify deterministic blocking reason(s).
4. The ledger MUST NOT create, promote, or mutate ClaimStatus.
5. Evidence references are provenance pointers, not substitute evidence.
6. Missing evidence references cannot support QUALIFIED.
7. Conflicting VERIFIED evidence MUST remain visible and MUST NOT be silently discarded.
8. Serialization MUST be deterministic for identical evaluation inputs.
9. Records are append-only; correction requires a new evaluation/decision record.
10. No API, network, or runtime side effect is required.

## Criterion result schema

Each criterion result MUST contain:
- `requirement_id`;
- `status`: `SATISFIED` or `UNSATISFIED`;
- `claim_refs`;
- `reason_code`;
- `observed_value` where applicable;
- `expected_value`;
- `operator`.

`SATISFIED` is valid only when matching required evidence is VERIFIED.

## Deterministic reason codes

Minimum codes:
- `MISSING_REQUIRED_EVIDENCE`
- `EVIDENCE_NOT_VERIFIED`
- `VALUE_MISMATCH`
- `TYPE_INCOMPATIBLE`
- `UNSUPPORTED_OPERATOR`
- `CONFLICTING_VERIFIED_EVIDENCE`
- `AMBIGUOUS_REQUIREMENT`
- `PROVENANCE_INCOMPLETE`

No free-form explanation may override a deterministic reason code.

## Decision semantics

`QUALIFIED` requires every required criterion to be SATISFIED with matching VERIFIED evidence and no unresolved required conflict.

`INCONCLUSIVE` applies when any required criterion is unsatisfied/unresolved, evidence/provenance is insufficient, or the requirement set is empty/ambiguous under the qualification contract.

The ledger records the decision trace; it does not independently alter qualification semantics.

## Provenance chain

The ledger MUST preserve references allowing reconstruction of:
`decision → requirement → criterion result → claim → observation → source/raw value → normalization outcome → EvidencePolicy decision`.

The ledger MUST NOT replace upstream raw evidence or EvidencePolicy records.

## Compatibility

PR #258 observation/claim identity; PR #259 source provenance; PR #260 normalization outcomes; PR #261 normalization vectors; PR #262 adapter→normalization provenance/error propagation; PR #263 sole OBSERVED→VERIFIED boundary; PR #264 deterministic qualification; PR #265 requirement outcome vectors.

## Scope exclusions

No runtime implementation, database/storage implementation, API calls, credentials, executed tests, workflow changes, or `src/jamp/run.py` changes.

## Repository invariants

Parent PR #265 HEAD: c6f87f64fa968b004d3868d4b8cc2584fd8c5737.
Frozen Core blob: 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a.
Required Frozen Core delta: 0.

## Status

DESIGN-ONLY / PRE-IMPLEMENTATION
