# Marketplace Parser → AEW → Qualification Runtime Implementation Contract v0.1

Status: DESIGN-ONLY / PRE-IMPLEMENTATION

## 1. Purpose

Define the runtime implementation boundary for Marketplace Parser → AEW EvidenceRecord/Ledger → deterministic Qualification. This contract specifies orchestration, interfaces, state transitions, provenance preservation, and fail-closed behavior. It does not implement runtime behavior, marketplace transport, AI/API calls, or CI.

## 2. Runtime pipeline

The implementation MUST execute: Marketplace adapter → RawObservation → deterministic normalizer → AEW Claim/EvidenceRecord → EvidencePolicy → Evidence Ledger snapshot → deterministic Qualification → Qualification Decision audit record.

No stage may skip a preceding required boundary.

## 3. Runtime inputs and outputs

Parser input MUST identify marketplace, source locator, retrieval context, and raw payload. Parser output MUST contain observation_id, marketplace, source_locator, observed_at, retrieved_at when applicable, raw_value, canonical_attribute, normalized_value when available, and status OBSERVED | UNKNOWN. Parser output MUST never be VERIFIED.

For marketplace observations, AEW mapping is normative:
- RawObservation.observation_id → EvidenceRecord.source_id;
- RawObservation.retrieved_at → EvidenceRecord.metadata.retrieved_at;
- source_type = marketplace observation;
- raw_hash MUST bind the preserved raw representation;
- claim_id/evidence_id MUST remain deterministic references.

AEW MUST NOT reinterpret marketplace values or promote evidence status.

Qualification consumes deterministic requirements and Claims whose evidence status has been evaluated by EvidencePolicy plus an immutable Ledger snapshot. Output is exactly QUALIFIED or INCONCLUSIVE. FAILED and NOT_QUALIFIED are not qualification results.

## 4. State machine

The runtime MUST enforce: RAW → OBSERVED/UNKNOWN → POLICY-EVALUATED → LEDGER-SNAPSHOT → QUALIFIED/INCONCLUSIVE.

Invalid transitions MUST fail closed. OBSERVED → VERIFIED is permitted only through EvidencePolicy; parser output → QUALIFIED and AI/model output → QUALIFIED are prohibited.

## 5. Provenance and identity invariants

The implementation MUST preserve:
observation_id → claim_id → evidence_id → ledger_snapshot_digest → requirement_evaluation_digest → decision_digest

and, where present:
retrieved_at → EvidenceRecord.metadata.retrieved_at.

The implementation MUST NOT substitute a newer observation under an existing identity, mutate source_locator/raw/normalized value under an existing observation identity, silently replace a marketplace source, or collapse multiple contributing observations without retaining all IDs. Provenance/digest integrity does not imply truth verification. Missing required links produce INCONCLUSIVE.

## 6. Fail-closed runtime behavior

Return INCONCLUSIVE when required source identity, raw representation/hash, provenance, EvidencePolicy evaluation, required VERIFIED evidence, conflict resolution, requirement input, ledger snapshot identity/digest, or decision audit inputs are missing/inconsistent/unresolved. No fallback may silently reinterpret or promote evidence.

## 7. Determinism and idempotency

Equivalent frozen canonical inputs, requirements, policy-evaluated Claims, and evidence scope MUST produce the same qualification result. New retrievals MUST receive new observation identities. Decision identity follows audited #271; canonical input changes require a new decision identity/digest.

## 8. Error boundary

Transport/extraction errors belong to the marketplace adapter. Normalization errors follow the parser contract. Evidence-policy uncertainty remains unresolved evidence. Qualification MUST NOT convert upstream operational errors into QUALIFIED. Structured provenance/error data MUST remain available for an INCONCLUSIVE audit record.

## 9. AI executor boundary

Gemini / Claude / GPT adapters remain observational components. Their output MUST enter the evidence pipeline as observations/claims subject to EvidencePolicy and MUST NOT directly determine qualification. ModelBudgetPolicy governs budget, timeout, retry, and provider-specific behavior.

## 10. Offline execution and testability

The runtime MUST support offline fixture mode using the frozen marketplace fixture/test-vector contracts, without marketplace/API calls, while preserving identical RawObservation → AEW → Ledger → Qualification semantics. Fixture identity MUST remain distinguishable from live source identity. Implementation must be testable against #261/#265 vectors and #270 compatibility rules.

## 11. Compatibility

Consumes without redefining: #267 Marketplace Parser Runtime Contract; #270 compatibility correction; AEW v0.1 EvidenceRecord/EvidenceLedger; Evidence Acquisition Contract v0; #264 Qualification Contract; #265 test vectors; #271 Decision/Evidence Ledger Contract; #272 Marketplace → AEW Provenance Contract; #273 correction.

## 12. Non-goals

No marketplace HTTP/headless transport; Ozon/WB/Yandex Market production extraction; Gemini/Claude/GPT SDK integration; EvidencePolicy/Ledger/Qualification implementation; CI/workflow changes; test-suite changes; or Frozen Core changes.

## 13. Frozen Core

src/jamp/run.py MUST remain unchanged.

Locked blob: 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a

Required: Δ(src/jamp/run.py) = 0

## 14. Freeze rule

Design-only runtime implementation contract. Runtime conformance requires a separate implementation PR and deterministic test execution. Normative changes to pipeline, provenance mapping, state machine, or qualification boundary require a new contract version.
