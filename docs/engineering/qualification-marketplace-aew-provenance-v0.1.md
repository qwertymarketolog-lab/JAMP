# Qualification Decision / Marketplace → AEW Provenance Contract v0.1

Status: DESIGN-ONLY / PRE-IMPLEMENTATION

## 1. Purpose

Define the provenance boundary from marketplace parser observations through
AEW Evidence Records into the Qualification Decision Audit Record.

Boundary:

```
Marketplace Parser
  RawObservation
       |
       v
AEW EvidenceRecord
       |
       v
Evidence Ledger snapshot
       |
       v
Qualification requirement evaluation
       |
       v
Qualification Decision Audit Record
```

This contract records provenance identity and binding rules only. It does not
execute parsing, call marketplace APIs, call AI providers, evaluate
qualification, or modify the Evidence Ledger.

## 2. Source observation identity

Every marketplace observation used by AEW MUST retain:

- `observation_id`: globally unique immutable observation identity;
- `marketplace`: source marketplace identifier;
- `source_locator`: source product/page/API locator;
- `observed_at`: observation timestamp;
- `retrieved_at`: retrieval timestamp, when applicable;
- `raw_value`: exact observed source value;
- `canonical_attribute`: normalized JAMP attribute identity;
- `normalized_value`: deterministic normalized value, when available;
- `status`: parser observation status.

Parser status is limited to `OBSERVED` or `UNKNOWN`. Parser provenance MUST
NOT imply `VERIFIED`.

The parser observation identity MUST remain distinguishable from the later
AEW evidence identity.

## 3. AEW evidence binding

An AEW EvidenceRecord derived from a marketplace observation MUST preserve a
deterministic reference to the source observation:

- `evidence_id`;
- `claim_id`;
- `source_type` = marketplace observation;
- `source_id` = `observation_id`;
- `raw_hash` over the preserved raw observation representation;
- `scope`;
- `status`;
- existing AEW provenance fields.

The EvidenceRecord MUST NOT rewrite the source observation into a new
untraceable value.

A missing source observation, missing raw hash, or unresolved source identity
MUST prevent downstream qualification from treating the evidence as
sufficient; the result is `INCONCLUSIVE`.

## 4. Observation → claim mapping

The mapping MUST be explicit:

```
observation_id
      |
      v
claim_id
      |
      v
evidence_id
      |
      v
ledger_snapshot_digest
      |
      v
requirement_evaluation
      |
      v
decision_digest
```

One observation MAY support one or more claims only when each mapping is
explicit and deterministic.

One claim MAY reference multiple observations. Multiple observations MUST NOT
be collapsed into one source identity without retaining all contributing
observation IDs.

## 5. Normalization boundary

The marketplace parser/normalizer is responsible for producing the canonical
attribute/value representation according to the existing normalization
contract.

Qualification MUST consume the canonical representation already supplied by
the upstream contract.

Qualification MUST NOT:

- reinterpret raw marketplace strings;
- perform implicit unit conversion;
- infer missing attributes;
- promote parser `OBSERVED`/ `UNKNOWN` to `VERIFIED`.

EvidencePolicy remains the sole promotion boundary for evidence status.

## 6. Provenance digest chain

For a marketplace-backed qualification, the minimum chain is:

```
raw_observation_bytes
        |
        v
observation_digest
        |
        v
observation_id
        |
        v
claim_id
        |
        v
evidence_id -> evidence_digest
        |
        v
ledger_snapshot_digest
        |
        v
requirement_evaluation_digest
        |
        v
decision_digest
```

Each link MUST be resolvable from the frozen audit record or its declared
immutable evidence scope.

A digest proves content integrity for the represented object. It does not,
by itself, prove when, where, or by whom the observation was obtained.

## 7. Decision Audit Record binding

A Qualification Decision Audit Record consuming marketplace evidence MUST
retain, directly or through immutable references:

- requirement identity;
- evidence scope identity;
- ledger snapshot identity/digest;
- evidence IDs and digests;
- claim IDs;
- source observation IDs;
- observation/raw digests;
- checker identity/version/digest;
- requirement evaluation digests;
- canonical decision digest.

The audit record MUST therefore support reconstruction:

```
decision
  -> requirement evaluation
  -> evidence record
  -> claim
  -> marketplace observation
  -> raw observation representation
```

If any required link cannot be reconstructed deterministically, the
qualification result MUST remain `INCONCLUSIVE`.

## 8. Source identity and substitution rules

The following are prohibited:

- replacing a referenced observation with a newer observation without a new
  evidence/decision identity;
- changing `source_locator` without creating a new observation identity;
- changing raw or normalized value under an existing observation identity;
- silently replacing one marketplace source with another;
- treating marketplace metadata as evidence verification.

A new observation is a new observation identity, even when its canonical value
is identical to an earlier observation.

## 9. Cross-layer invariants

1. Marketplace parser emits only `OBSERVED`/`UNKNOWN`.
2. AEW preserves observation provenance; it does not invent source identity.
3. EvidencePolicy remains the sole `OBSERVED → VERIFIED` boundary.
4. Qualification consumes only policy-evaluated evidence.
5. Qualification result remains exactly `QUALIFIED` or `INCONCLUSIVE`.
6. Missing or conflicting provenance fails closed.
7. AI/model output may be an observation but cannot be the qualification oracle.
8. No layer silently mutates an upstream immutable identity.
9. Equivalent frozen canonical inputs produce identical deterministic
   qualification outcomes.
10. Provenance integrity does not imply truth verification.

## 10. Compatibility

This contract consumes, without redefining:

- Marketplace Parser Runtime Contract v0.1 (#267);
- Offline Marketplace Fixture Contract v0.1 / compatibility correction (#270);
- AEW v0.1 EvidenceRecord / EvidenceLedger;
- Evidence Acquisition Contract v0;
- deterministic Qualification Contract v0.1.1 (#264);
- Qualification Requirement Test Vectors v0.1.1 (#265);
- Qualification Decision / Evidence Ledger Contract v0.1 (#271).

No runtime/API/CI/test implementation is introduced.

## 11. Non-goals

This contract does not implement:

- marketplace transport or extraction;
- parser runtime;
- AI provider/API calls;
- EvidencePolicy implementation;
- Evidence Ledger implementation;
- qualification runtime;
- decision execution;
- CI/workflow changes;
- test-suite changes;
- Frozen Core changes.

## 12. Frozen Core

`src/jamp/run.py` MUST remain unchanged.

Locked blob:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Required:

`Δ(src/jamp/run.py) = 0`

## 13. Freeze rule

This is a design-only contract. Runtime conformance requires a separate
implementation and deterministic test-vector contract.

Any normative change to observation identity, evidence binding, provenance
canonicalization, or decision reconstruction requires a new contract version.
