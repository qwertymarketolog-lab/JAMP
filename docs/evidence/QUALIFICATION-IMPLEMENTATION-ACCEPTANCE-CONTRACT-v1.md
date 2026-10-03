# Qualification / Implementation Acceptance Contract v1

**Status:** DESIGN-ONLY / PRE-IMPLEMENTATION  
**Baseline:** c18fd307622c195e5b62cae094292f3f2b6b88a9  
**Related Evidence Acquisition implementation contract:** 9baa68980c482f588237b9798e90d495c2aa4af7  
**Scope:** qualification-layer and implementation-acceptance requirements A–I identified by the read-only v1↔v0 scope audit.  
**Frozen Core:** src/jamp/run.py blob 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a — LOCKED, Δ=0.  
**Protected workflow:** .github/workflows/import-historical.yml — NO CHANGE.

## 1. Purpose and boundary

This contract isolates requirements not directly specified by Evidence Acquisition Contract v0 but required for qualification-layer implementation and acceptance.

It MUST NOT redefine Evidence Acquisition v0. Execution identity, frozen input, raw output, atomic observations, deterministic checker, immutable bundle, integrity chain, and offline replay remain governed by v0.

This document is DESIGN-ONLY. It does not implement or claim runtime conformance.

Fail-closed rule: missing, conflicting, malformed, or unverifiable evidence MUST NOT produce a positive qualification result.

## 2. Persisted Evidence Ledger

An implementation claiming this contract MUST provide durable append-only persistence.

Each persisted entry MUST contain ledger_entry_id, evidence record, record_digest, previous_entry_digest, creation metadata, and immutable evidence identity. Duplicate evidence identities MUST be rejected.

Persistence MUST NOT promote OBSERVED evidence to VERIFIED. Verification remains explicit.

Ledger integrity failures include duplicate identities, broken previous-entry links, record-digest mismatch, and malformed records. Such failures are not successful qualification.

## 3. Deterministic Qualification Decision

The semantic decision MUST be the deterministic function of frozen_input, evidence_snapshot, requirement_set, and checker_identity.

Dynamic execution metadata MUST NOT alter semantic decision identity.

The decision_digest MUST exclude dynamic timestamps and equivalent nondeterministic metadata. Identical canonical frozen input, evidence snapshot, requirement set, and checker identity MUST produce the same decision digest.

The decision MUST bind to frozen input identity, evidence snapshot identity/digest, requirement-set identity/digest, and checker identity/version/source digest.

No undeclared current catalog/provider state may enter the semantic decision.

## 4. Qualification Verdict Semantics

The verdict set is QUALIFIED, INCONCLUSIVE, DISQUALIFIED.

- missing required evidence → INCONCLUSIVE;
- conflicting verified evidence → INCONCLUSIVE;
- verified mandatory requirement violation → DISQUALIFIED;
- all mandatory requirements verified and satisfied → QUALIFIED.

Absence of evidence MUST NOT be interpreted as satisfaction. A transport/API failure MUST NOT by itself become a semantic requirement violation.

## 5. Conflict Handling

Conflicting verified evidence for the same qualification attribute MUST NOT be collapsed by arbitrary precedence.

Unless a separate frozen requirement defines deterministic conflict resolution, the result MUST be INCONCLUSIVE.

The conflict and participating evidence identities MUST remain auditable.

## 6. Replay Verifier API Convention

The v0 replay operation MAY be exposed through a concrete verifier API. If adopted, an equivalent to ReplayVerifier.verify(bundle_path) SHOULD be provided.

The API name/signature is an implementation convention, not a new v0 semantic requirement.

The verifier MUST satisfy the v0 offline replay contract and MUST NOT use network/current provider state.

## 7. Acceptance Tests

The following are qualification/implementation acceptance tests:
1. append-only ledger/hash-chain behavior;
2. duplicate evidence identity rejection;
3. deterministic qualification decision digest;
4. verified mandatory violation → DISQUALIFIED;
5. conflicting verified evidence → INCONCLUSIVE;
6. replay API integration against the v0 offline replay contract.

Tests MUST be deterministic and fail closed.

## 8. Acceptance Gate

Conformance MUST NOT be declared until required ledger behavior, deterministic decision behavior, verdict semantics, and conflict handling are implemented and tested; v0 Evidence Acquisition conformance is independently established; terminal CI evidence exists for the exact implementation commit; required replay evidence is terminal; Frozen Core remains unchanged; .github/workflows/import-historical.yml remains unchanged; and no unresolved integrity/provenance conflict remains.

Design inspection alone is insufficient for runtime conformance.

## 9. Non-goals

This contract does NOT authorize modification of src/jamp/run.py, .github/workflows/import-historical.yml, historical evidence, historical R18–R30 evidence, or qualification thresholds. It does not authorize upgrading missing evidence to VERIFIED or treating CI absence/empty jobs as PASS.

## 10. Traceability

This contract contains the scope additions identified in the read-only audit of implementation contract v1 against Evidence Acquisition v0:
- A: persisted Evidence Ledger;
- B: deterministic semantic qualification decision;
- C: qualification verdict semantics;
- D: concrete replay-verifier API convention;
- E/F: ledger acceptance tests;
- G: deterministic decision-digest test;
- H: DISQUALIFIED acceptance test;
- I: conflict → INCONCLUSIVE semantics.

Underlying evidence/replay semantics remain governed by Evidence Acquisition v0.

## 11. Frozen Core Invariant

SHA256(src/jamp/run.py) MUST remain 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a.

Expected: Δ(src/jamp/run.py) = 0

Any Core change requires a separate explicit Core Unlock decision.

## 12. Design Status

**DESIGN-ONLY / PRE-IMPLEMENTATION**

No implementation conformance is claimed by this document.
