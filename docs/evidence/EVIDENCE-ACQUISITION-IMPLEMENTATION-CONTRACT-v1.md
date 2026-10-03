# Evidence Acquisition Implementation Contract v1

**Status:** DESIGN-ONLY / PRE-IMPLEMENTATION  
**Baseline:** c18fd307622c195e5b62cae094292f3f2b6b88a9  
**Frozen Core:** src/jamp/run.py blob 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a — LOCKED, Δ=0  
**Protected workflow:** import-historical.yml — NO CHANGE

## 1. Purpose and conformance boundary

This document defines the minimum implementation contract required for a future implementation to claim conformance with Evidence Acquisition Contract v0. It is design-only and does not implement or claim conformance.

The implementation must be additive. Missing evidence, failed tests, or unverifiable provenance MUST result in HOLD / INCONCLUSIVE, never synthetic PASS. Historical artifacts MUST NOT be rewritten.

## 2. Required components

### 2.1 ExecutionEnvelope

Immutable pre-execution record containing at minimum:
contract_version, execution_id, execution_created_at, execution_started_at, execution_finished_at, git_sha, probe_sha, workflow_sha, target_ref, entrypoint, pid, process_started_at, cwd, runtime_identity, environment_digest, argv_digest, input_digest, spec_hash, criterion_set_hash, implementation_ref, environment_ref, status.

The envelope MUST exist before external/model execution. execution_id MUST bind the complete execution chain.

### 2.2 Frozen input

Persist canonical frozen input with execution_id, probe_id, model_id, canonical task/input, encoding version, input_digest, timestamp, and contract/checker version. Equivalent canonical inputs MUST produce the same digest.

### 2.3 Raw transport/output

Persist execution_id, request/input digest, provider endpoint, HTTP/status, allowlisted headers, exact raw response/content-addressed object, raw_response_digest, elapsed transport, response timestamp, and terminal transport state. Secrets MUST be excluded.

### 2.4 Atomic observation

Bind execution_id, frozen-input digest, raw-output digest, probe_id, operator_id/version, observation content, and observation identity. Neutral observation records MUST NOT contain semantic qualification verdicts.

### 2.5 Persisted Evidence Ledger

The logical EvidenceLedger API may remain, but conformance requires durable append-only persistence. Each entry contains ledger identity, evidence record, record digest, previous-entry digest, and creation metadata. Duplicate evidence identities MUST be rejected. Persistence MUST NOT promote OBSERVED to VERIFIED.

### 2.6 Deterministic checker

Every checker declares checker_id, checker_version, checker_source_ref, checker_source_digest, input schema/version, canonicalization rules, required input digests, output schema, acceptance/rejection/inconclusive predicates, and self-test/reference fixtures.

checker_source_digest MUST hash the canonical checker implementation, not merely a logical identifier. Missing, malformed, conflicting, or unverifiable required inputs MUST fail closed.

### 2.7 Deterministic decision

Semantic decision computation is:

decision = F(frozen_input, evidence_snapshot, requirement_set, checker_identity)

Dynamic timestamps MUST NOT participate in semantic decision_digest. Identical canonical inputs and identical evidence/checker state MUST yield the same decision_digest. Execution/bundle timestamps may remain metadata.

### 2.8 Verdicts

The verdict enum MUST contain QUALIFIED, INCONCLUSIVE, DISQUALIFIED.

- missing required evidence → INCONCLUSIVE
- conflicting evidence → INCONCLUSIVE
- verified mandatory requirement violation → DISQUALIFIED
- all mandatory requirements verified and satisfied → QUALIFIED

No verdict may be synthesized from absence of evidence.

### 2.9 Immutable Evidence Bundle

A self-contained content-addressed bundle MUST include a manifest containing bundle_version, execution_id, execution_envelope_digest, frozen_input_digest, raw_output_digest, atomic observation IDs, checker_id/version/digest, checker input/output digests, final status, creation timestamp, and bundle_digest.

The bundle must contain sufficient raw/provenance/evidence material for offline verification. Historical bundles remain unchanged.

### 2.10 ReplayVerifier

Provide an offline verifier equivalent to ReplayVerifier.verify(bundle_path).

It MUST validate manifest/bundle digests, execution identity, frozen-input/raw-output bindings, observation/evidence identities, checker identity/version/source digest, rerun the declared checker on frozen inputs, compare checker output and decision_digest, and emit a terminal replay status.

Replay statuses: REPLAY_VERIFIED, REPLAY_INCONCLUSIVE, INTEGRITY_FAILURE.

Replay MUST use no network, current provider/catalog state, or undeclared external input. Checker mismatch MUST be REPLAY_INCONCLUSIVE, not silently upgraded.

## 3. Integrity chain

git_sha → probe_sha/workflow_sha → execution_id → input_digest → raw_response_digest → atomic_observation_id → checker_digest → checker_output_digest → bundle_digest

Digest equality proves content equality; it does not by itself prove real-world execution causality.

## 4. State machine

Required states:
DESIGNED → PREFLIGHT_VERIFIED → EXECUTING → CAPTURED → CHECKED → BUNDLED → REPLAY_VERIFIED

Failure states remain explicit: FAILED, INCONCLUSIVE, INTEGRITY_FAILURE. Missing data MUST NOT cause implicit transitions.

## 5. Mandatory conformance tests

At minimum:
1. execution identity binding
2. frozen-input digest reproducibility
3. raw-output/execution binding
4. immutable bundle integrity
5. append-only ledger/hash-chain behavior
6. duplicate evidence rejection
7. checker source digest sensitivity to source changes
8. deterministic decision digest
9. verified violation → DISQUALIFIED
10. missing evidence → INCONCLUSIVE
11. conflicting evidence → INCONCLUSIVE
12. offline replay → REPLAY_VERIFIED
13. corrupted bundle → INTEGRITY_FAILURE
14. checker mismatch → REPLAY_INCONCLUSIVE
15. replay performs no network access

Terminal CI evidence is required before conformance is declared.

## 6. Non-goals

This contract does not authorize modification of src/jamp/run.py, import-historical.yml, historical evidence, qualification thresholds, historical R18–R30 evidence, or existing provenance identities.

## 7. Frozen Core invariant

SHA256(src/jamp/run.py) MUST remain 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a. Expected Δ(src/jamp/run.py) = 0.

Any Core change requires a separate explicit Core Unlock decision and is outside this contract.

## 8. Implementation acceptance gate

Conformance may be declared only after all mandatory components and tests exist, terminal CI passes on the exact implementation commit, Frozen Core and import-historical.yml remain unchanged, replay evidence is terminal, and no unresolved integrity/provenance conflict remains.

Until then:

**CONFORMANCE = UNKNOWN / HOLD**

## 9. Design status

**DESIGN-ONLY / PRE-IMPLEMENTATION**

This specification defines the implementation boundary; it is not implementation evidence.
