# AuditTrace Contract v0.1 — Read-only P0 audit

- Audit date: 2026-10-26
- Repository: qwertymarketolog-lab/JAMP
- Documentation branch: docs/audit-trace-contract-p0-20261026 (branched from main)
- Scope: document ProvenanceTracker.create_trace(), AuditPersistence, relevant tests, and the requested Real Pilot evidence. No Python/runtime code changed.
- Frozen Core: src/jamp/run.py blob SHA observed as 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a, matching the locked blob. Δ = 0.

## 1. Evidence sources and limits

| Source | Observed evidence | Limitation |
|---|---|---|
| [provenance.py](../../src/jamp/runtime/provenance.py) | AUDIT_TRACE_SCHEMA_VERSION is jamp-audit-trace-v0.2; create_trace() emits the fields below; validator accepts v0.1 and v0.2 | Code contract, not a formal JSON Schema. |
| [persistence.py](../../src/jamp/runtime/persistence.py) | Append-only JSONL; sorted-key JSON serialization; newline terminator; flush + fsync; lookup by trace_id scans line-by-line | Validates only non-empty trace_id; no full-schema validation or uniqueness enforcement. |
| [test_audit_persistence.py](../../tests/test_audit_persistence.py) | Write/read round-trip, required trace_id, restart persistence, REFUSE trace persistence | Fixtures are partial traces; they do not prove all production field combinations. |
| [test_audit_exporter.py](../../tests/test_audit_exporter.py) | Schema-version checks, incremental cursor, idempotent batches, partial-line handling, retry behavior, payload hash and trace identity preservation | Most S3 behavior uses a mocked adapter; this is not proof of a production bucket. |
| [Real Pilot Run 40314338566](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/40314338566) | Job 121543043161 concluded success; artifact 12645573886 exists and is not expired; run head SHA 940fec7c495ff2c890ff69b34f655e604fb20f68 | Downloaded artifact contains real-pilot.log and artifacts/real-pilot/uvicorn.log, but no provenance.json. Log reports trace_id trace_a0e5d28e, provider response ID, evidence status, and signature result, but not the full persisted AuditTrace object. Field-by-field comparison with the actual record is therefore NOT POSSIBLE from this artifact. |
| [real-pilot.yml](../../.github/workflows/real-pilot.yml) | Upload step includes only real-pilot.log and artifacts/real-pilot/uvicorn.log | Explains why provenance.json is absent; this audit does not change the workflow. |

## 2. create_trace() output contract

“Required” means emitted unconditionally by the producer, not validated by AuditPersistence.

| JSON path | Type / shape | Emission rule | Migration treatment |
|---|---|---|---|
| schema_version | string | Always; currently jamp-audit-trace-v0.2 | IMMUTABLE — preserve exact version. |
| trace_id | string | Always; trace_<8 hex chars> | IMMUTABLE — audit identity; never regenerate. Persistence requires non-empty value. |
| timestamp | string, UTC ISO-8601 | Always | IMMUTABLE — event time cannot be safely reconstructed. |
| request_id | string | Caller value or generated req_<8 hex chars> | IMMUTABLE — request/trace correlation. |
| status | string | action argument | IMMUTABLE — historical decision outcome. |
| task_profile | string | Always | IMMUTABLE — decision context. |
| required_capabilities | array of strings | required_caps tuple serialized as a list | IMMUTABLE — original capability requirements. |
| gate_evaluator | object | Always | IMMUTABLE — decision/evidence metadata. |
| gate_evaluator.evidence_base_sha256 | string | Always; EVIDENCE_SHA256 constant | IMMUTABLE — preserve exact digest. |
| gate_evaluator.eligible_models_count | integer | eligible_count argument | IMMUTABLE — historical count, not a live count. |
| evidence_hashes | object | Always | IMMUTABLE. |
| evidence_hashes.raw_artifact_sha256 | string | Always; same current constant as evidence base | IMMUTABLE — preserve exact digest. |
| frozen_core_state | object | Always | IMMUTABLE — historical Frozen Core observation. |
| frozen_core_state.blob | string | Always; locked blob SHA | IMMUTABLE. |
| frozen_core_state.delta | integer | Always; currently 0 | IMMUTABLE — do not normalize. |
| frozen_core | object | Always; compatibility representation duplicates some fields | IMMUTABLE — preserve duplicate representation too. |
| frozen_core.path | string | Always; src/jamp/run.py | IMMUTABLE. |
| frozen_core.blob | string | Always; locked blob SHA | IMMUTABLE. |
| frozen_core.delta | integer | Always; currently 0 | IMMUTABLE. |
| execution_details | object | Present when status/action is EXECUTE | IMMUTABLE — preserve full object as written. |
| execution_details.selected_model | string | Always inside execution_details | IMMUTABLE. |
| execution_details.evidence_status | string | Only when argument is not None | IMMUTABLE. |
| execution_details.evidence_details | object of selected non-empty strings | Optional; allowlisted keys: reason, error, provider_model, provider_name, generation_id, jamp_model | IMMUTABLE — missing keys cannot be inferred. |
| execution_details.provider | string | If output contains a non-empty string | IMMUTABLE. |
| execution_details.requested_model_id | string | If output contains a non-empty string | IMMUTABLE. |
| execution_details.provider_requested_model_id | string | If output contains a non-empty string | IMMUTABLE. |
| execution_details.provider_model_id | string | If output contains a non-empty string | IMMUTABLE. |
| execution_details.provider_response_id | string | If output contains a non-empty string | IMMUTABLE. |
| execution_details.crosswalk_digest | string | If output contains a non-empty string | IMMUTABLE. |
| execution_details.qualification | string | Output string if non-empty; otherwise UNKNOWN | IMMUTABLE — never backfill stronger qualification from current data. |
| execution_details.fallback_history | array of objects | If a list is supplied; first 5 valid entries; provider, requested_model, http_status integer 100–599, error string; string values length-limited | IMMUTABLE — preserve attempts and order. |
| execution_details.output_digest | string, sha256:<hex> | If output is not None; digest uses sorted-key compact JSON | IMMUTABLE — digest cannot reconstruct original output. |
| refusal_details | object | Present when status/action is not EXECUTE | IMMUTABLE. |
| refusal_details.reason | string | Caller reason or FAIL_CLOSED_ZERO_QUALIFIED_MODELS | IMMUTABLE. |
| refusal_details.message | string | Constructed from refusal reason or required capabilities | IMMUTABLE — preserve exact message. |
| refusal_details.provider_diagnostics | object | Optional; only if filtered diagnostics are non-empty | IMMUTABLE — preserve exact recorded subset. |
| refusal_details.provider_diagnostics.evidence_status / reason / error / provider_model / generation_id / jamp_model / provider_name / http_status / network_error / exception_type / error_message / error_body | JSON values copied when key exists | Optional; source values are not uniformly type-checked | IMMUTABLE — preserve observed values, do not normalize silently. |
| refusal_details.provider_diagnostics.code / finish_reason / model / selected_model / requested_model_id / provider_requested_model_id / crosswalk_digest / output_provider / output_response_id / output_model_id | Usually non-empty strings; finish_reason may explicitly be null | Optional allowlisted values | IMMUTABLE. |
| refusal_details.provider_diagnostics.usage | object | Optional; copied if source is a dict | IMMUTABLE. |
| refusal_details.provider_diagnostics.fallback_history | array of filtered objects | Optional; same max-five and field rules as execution history | IMMUTABLE. |
| refusal_details.provider_diagnostics.content_len / reasoning_len / requested_max_tokens / provider_http_status | non-negative integers | Optional; strict integer check | IMMUTABLE. |

Note: several refusal diagnostic keys are copied without strict per-field type validation. Persistence serializes the result; it does not normalize or validate these values. The code producer is the best current description of the emitted shape, but not a complete formal schema.

## 3. Immutable vs mutable/reconstructible

### Immutable — preserve as source evidence
All fields generated by create_trace() above must be treated as immutable historical facts during migration. Preserve original JSON values, unknown additional keys in legacy records, missing optional fields, and original schema version. Do not recompute timestamps, counts, status, provider IDs, qualification, digests, refusal text, or Frozen Core fields.

### Mutable / reconstructible — derived operational data only
The current AuditTrace contract defines NO mutable/reconstructible fields. Operational data such as a database surrogate key, ingestion timestamp, search index, or materialized projection may be added separately, but must not overwrite the source trace.

organization_id and user_id are NOT present in the current trace contract. Historical ownership cannot be safely reconstructed from the trace alone. Do not infer ownership from request IDs, timestamps, provider IDs, Telegram identifiers, or coincidental values. Backfill only from an independent, documented source; otherwise leave ownership UNKNOWN and deny tenant access by default.

## 4. Persistence and exporter guarantees observed in tests

- write_trace() rejects missing/empty trace_id; it does not validate the full schema.
- JSONL uses UTF-8, ensure_ascii=False, sort_keys=True, one JSON object per newline.
- Each write calls flush() and os.fsync().
- read_trace_by_id() returns the first matching trace_id and scans sequentially. Duplicate IDs are not rejected.
- Tests cover round-trip fidelity, refusal trace persistence across app restart, partial final line behavior in exporter, cursor retry/idempotency, payload SHA-256, batch identity, and provider response ID preservation.
- Export tests mostly use a mocked S3 adapter; they do not prove a production S3 deployment.

## 5. Constraints for PostgreSQL migration design

1. Keep the original serialized trace as canonical audit payload (or preserve exact original bytes plus a lossless JSON representation and source hash).
2. Keep schema version and every original key/value unchanged. New tenant metadata belongs in a separate envelope/relational mapping unless a future versioned contract explicitly defines it.
3. Never fabricate organization_id/user_id for historical rows. Unknown ownership remains unknown; access fails closed.
4. Preserve duplicate records and ordering/ingestion evidence; do not silently deduplicate by trace_id.
5. Before declaring migration complete, validate row counts, trace IDs, source payload hashes, schema-version distribution, and malformed/partial JSONL lines.
6. Define uniqueness constraints only after inventorying real historical data and deciding how duplicate trace IDs should be represented.
7. A successful import proves data migration only, not tenant isolation or API authorization.

## 6. Audit verdict

VERIFIED
- Producer contract is jamp-audit-trace-v0.2; validator accepts v0.1 and v0.2.
- Persistence is append-only JSONL with flush/fsync and trace-id lookup.
- Frozen Core blob SHA matches the locked SHA.
- Real Pilot Run 40314338566 has a terminal successful job and a retained artifact.

HOLD / UNKNOWN
- Full Real Pilot provenance.json was not included in artifact 12645573886; the actual serialized record from that run cannot be compared field-by-field from retained evidence.
- Tests do not define a complete formal schema or establish production database, tenant ownership, or authorization behavior.
- Historical tenant ownership is absent from the trace contract.

STATE: HOLD — AuditTrace contract documented; PostgreSQL / Organization / User / KeyManager implementation is not authorized by this document. Next evidence step is to correct the Real Pilot diagnostic artifact in a separately reviewed change and capture the actual persisted provenance object, then compare it against this contract.
