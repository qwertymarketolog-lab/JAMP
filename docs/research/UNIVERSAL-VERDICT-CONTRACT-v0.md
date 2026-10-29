# Universal Verdict Contract v0

**Status:** normative design contract; implementation scope is a data skeleton only.  
**Version:** `uv0.1.0`

## 1. Purpose and boundary

Universal Verdict is a provenance envelope for a bounded result. Hashes bind declared inputs and output; they do not independently establish truth. `JampVerdict` remains unchanged and is retained in full as the execution-layer artifact. `execution_ref.jamp_verdict_hash` links to it by the normative hash below; Universal Verdict does not embed a rewritten or reduced replacement. v0 does not integrate with the API or perform aggregation.

## 2. Fields

| Field | Type | Meaning |
|---|---|---|
| `spec_ref` | `SpecRef {spec_id, spec_hash}` | Specification identity and content hash fixed before execution. |
| `criteria_ref` | `CriteriaRef {criteria_id, criteria_hash}` | Criteria identity and content hash fixed before execution. |
| `execution_ref` | `ExecutionRef {jamp_verdict_hash, execution_status}` | Link to the unchanged, separately retained `JampVerdict`. |
| `evidence_refs` | `tuple[EvidenceRef, ...]` | Immutable references; each item is `{type, ref_hash, source_sha256}`. |
| `classification` | `UniversalClassification {label, classification_hash}` | Normative Universal Classification, not `TaskClassifier` output. |
| `verdict` | `VerdictResult {result, verdict_hash}` | Result and its payload hash. |
| `verifier` | `VerifierInfo {version, reproducible, aggregation_rule_hash}` | Contract version, independent reproducibility flag, hash of deterministic aggregation-rule description. |
| `timestamp` | ISO-8601 UTC string | For example, `2026-10-29T12:00:00Z`. |
| signature | returned by `sign(secret)` | HMAC-SHA256 over `verdict_hash`; excluded from the hashed payload. |

`VerdictResult.result` is restricted in v0 to `VERIFIED`, `CONTRADICTED`, `INCONCLUSIVE`, or `PARTIAL`. No other result label is valid in v0.

Evidence reference types are extensible: examples include `raw_document`, `api_response`, and `db_row`. `ocr_block` is reserved as an OCR extension point; no OCR implementation is included.

## 3. Canonicalization

The single canonical JSON formula for hash payloads is:

```python
json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
```

This sorted-key, compact JSON serialization is normative wherever this contract requires canonical bytes. NaN and infinities are forbidden.

## 4. Normative algorithm: `jamp_verdict_hash`

```
jamp_verdict_hash := "sha256:" + hex(SHA-256(canonical_bytes(jamp_verdict_payload)))
```

where:

- `jamp_verdict_payload = JampVerdict._payload()` — all fields except `signature`;
- `canonical_bytes` is the formula in §3;
- serialization is exactly the one used by `JampVerdict.sign()`.

The helper `compute_jamp_verdict_hash(jv)` lives in `src/jamp/runtime/universal_verdict.py`, imports `JampVerdict`, and calls `jv._payload()`. It does not monkey-patch or modify `JampVerdict`. The `sha256:` prefix makes the digest algorithm explicit. Signature is excluded because it is derived from the payload; including it would introduce a circular dependency.

## 5. Normative algorithm: `verdict_hash`

```
verdict_hash := "sha256:" + hex(SHA-256(canonical_bytes(universal_verdict_payload)))
```

`universal_verdict_payload` is `UniversalVerdict.canonical_payload()`. It contains all Universal Verdict v0 fields except `verdict.verdict_hash` and any signature. The nested `verdict` object therefore contains only `result` during canonicalization. The digest is stored as `verdict.verdict_hash`; excluding that field prevents recursive hashing.

`classification_hash` is calculated over the canonical classification payload containing `label` and excluding `classification_hash`. The Universal Verdict payload includes the resulting `classification_hash`.

`sign(secret)` returns the hexadecimal HMAC-SHA256 of the UTF-8 `verdict_hash` string, keyed by `secret`. `verify(secret, sig)` recomputes that HMAC and uses constant-time comparison. Production callers use the existing `JAMP_SIGNING_KEY`; v0 introduces no new secret. Signature validity proves integrity under the key, not logical correctness.

## 6. Invariants v0

1. **Stable JampVerdict hash:** `jamp_verdict_hash` is computed from `JampVerdict._payload()` with the exact canonicalization used by `JampVerdict.sign()`; `signature` is excluded.
2. **Stable Universal Verdict hash:** `verdict_hash` is SHA-256 of the canonical Universal Verdict payload, excluding `verdict.verdict_hash` and signature.
3. **Pre-committed inputs:** `spec_hash` and `criteria_hash` identify fixed specification and criteria content before execution; they must not change after observing the result.
4. **Reproducibility is mandatory:** `reproducible` is a required boolean. It may be true only when an independent rerun using the referenced specification and criteria yields the same `verdict.result`. If `reproducible=false`, the verdict is **not confirmed**, even if its signature verifies.
5. **Normative classification:** `classification` is a Universal Classification object with its own canonical `classification_hash`; a routing/task classifier is not a substitute.
6. **Execution immutability:** the original `JampVerdict` is retained in full and unchanged. `execution_ref` links to it using `jamp_verdict_hash` and records `execution_status`.
7. **Evidence references are explicit:** `evidence_refs` is an immutable tuple in memory; each entry identifies its type, reference hash, and source SHA-256. `ocr_block` is reserved, not implemented.
8. **Versioned deterministic rules and signing:** `verifier.version` follows `uv0.x.y`; changes to hash/aggregation semantics require a version bump. `aggregation_rule_hash` hashes the deterministic rule description for mapping claim statuses to aggregate results. Aggregation implementation is out of scope. HMAC-SHA256 uses the existing signing secret and does not establish logical correctness.

**Conflict rule:** if relevant evidence conflicts and the conflict is unresolved, the result must remain `INCONCLUSIVE`; do not select a convenient status to conceal ambiguity.

## 7. What is not included in v0

- No independent full-chain verifier.
- No aggregation implementation.
- No API/runtime integration.
- No OCR processing; `evidence_refs[].type = "ocr_block"` is only a reserved extension point.
- No rewrite or modification of `JampVerdict`, `src/jamp/runtime/verdict.py`, `src/jamp/api/app.py`, or `src/jamp/runtime/evidence_gate.py`.
- No change to `src/jamp/run.py` (Frozen Core).
- `math_arith_001` remains DRAFT.

## 8. Examples

These are deterministic **synthetic fixtures**, not evidence about real executions or existing specification artifacts. Hashes are calculated for the fixture inputs and payloads shown; they must not be interpreted as repository evidence. For `verdict_hash`, the displayed `verdict.verdict_hash` is excluded during calculation.

### 8.1 VERIFIED

```json
{
  "spec_ref": {"spec_id": "demo.spec.v0", "spec_hash": "sha256:b2fa862ea3cfd6d0bcc30a16094e0a54485c7de67b2898ca677921c4afc58f66"},
  "criteria_ref": {"criteria_id": "demo.criteria.v0", "criteria_hash": "sha256:68e8225a3d7d2a1ea37a61854ac2bca4e9d9b21cd54319322e1b3bdd109e7d0e"},
  "execution_ref": {"jamp_verdict_hash": "sha256:3b5932eaf32a3bba52d3d15dec4b6e349e94e2ffb7926273a36291fa441d04c8", "execution_status": "EXECUTE"},
  "evidence_refs": [{"type": "api_response", "ref_hash": "sha256:4147175ca2b1ce4923ee78dd20f55462b242ae43d127fd15fc2edaab43984733", "source_sha256": "sha256:766c3840581d6234ebe9bf340d2efe1502d4288953917e706cf0bd297127712e"}],
  "classification": {"label": "FACTUAL_CLAIM", "classification_hash": "sha256:d3187ac9277f0453652e4f4a02d0f09cf0c99b3234b39544a184c53753fe0a0b"},
  "verdict": {"result": "VERIFIED", "verdict_hash": "sha256:1db94743eb3f0bea3bbde35ef7a781d5e81e34f75e9f427c74176582062df9b8"},
  "verifier": {"version": "uv0.1.0", "reproducible": true, "aggregation_rule_hash": "sha256:f97c454e4cb1c7cba4fcbe97dcec36d98edda4f2044ad499307154ec694d3dde"},
  "timestamp": "2026-10-29T12:00:00Z"
}
```

### 8.2 CONTRADICTED

```json
{
  "spec_ref": {"spec_id": "demo.spec.v0", "spec_hash": "sha256:b2fa862ea3cfd6d0bcc30a16094e0a54485c7de67b2898ca677921c4afc58f66"},
  "criteria_ref": {"criteria_id": "demo.criteria.v0", "criteria_hash": "sha256:68e8225a3d7d2a1ea37a61854ac2bca4e9d9b21cd54319322e1b3bdd109e7d0e"},
  "execution_ref": {"jamp_verdict_hash": "sha256:4b40d9b37a87c20a9e5d31e42fa8e6b103fc93faa7ba307da3a52c2ba6ff6d0b", "execution_status": "EXECUTE"},
  "evidence_refs": [{"type": "raw_document", "ref_hash": "sha256:dc38598fa121dcc40cc1c4dfc08557fd40275e33f849b59ffc72145e92db20e9", "source_sha256": "sha256:e35d35974f178117d52388f723bbced1b410cf84d3de8a0ada11bfbda738065a"}],
  "classification": {"label": "FACTUAL_CLAIM", "classification_hash": "sha256:d3187ac9277f0453652e4f4a02d0f09cf0c99b3234b39544a184c53753fe0a0b"},
  "verdict": {"result": "CONTRADICTED", "verdict_hash": "sha256:f9e67b0391646b1595f040f1849c674f4b19e951b384da75e30416d16bd6f402"},
  "verifier": {"version": "uv0.1.0", "reproducible": true, "aggregation_rule_hash": "sha256:f97c454e4cb1c7cba4fcbe97dcec36d98edda4f2044ad499307154ec694d3dde"},
  "timestamp": "2026-10-29T12:00:00Z"
}
```

### 8.3 INCONCLUSIVE

```json
{
  "spec_ref": {"spec_id": "demo.spec.v0", "spec_hash": "sha256:b2fa862ea3cfd6d0bcc30a16094e0a54485c7de67b2898ca677921c4afc58f66"},
  "criteria_ref": {"criteria_id": "demo.criteria.v0", "criteria_hash": "sha256:68e8225a3d7d2a1ea37a61854ac2bca4e9d9b21cd54319322e1b3bdd109e7d0e"},
  "execution_ref": {"jamp_verdict_hash": "sha256:1170a7d7248a12c75c95a82cb9eb20e1d31ab5ac89e099e3a4a22bf70110eb86", "execution_status": "REFUSE"},
  "evidence_refs": [],
  "classification": {"label": "UNRESOLVED", "classification_hash": "sha256:a237f85eeb592da6752b916e8ffe3876931ecee20ae6e5090e90e5ceee1cfe0b"},
  "verdict": {"result": "INCONCLUSIVE", "verdict_hash": "sha256:bf586752f05cdd0ffd85b86497e40cf0e71ae34127c005960bb6a4dc7c2ab169"},
  "verifier": {"version": "uv0.1.0", "reproducible": false, "aggregation_rule_hash": "sha256:f97c454e4cb1c7cba4fcbe97dcec36d98edda4f2044ad499307154ec694d3dde"},
  "timestamp": "2026-10-29T12:00:00Z"
}
```
