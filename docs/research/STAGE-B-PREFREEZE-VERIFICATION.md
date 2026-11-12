# Stage B — Pre-Freeze Verification Record

**Status:** OPEN / PRE-FREEZE  
**Base:** `main@fb6334b923ea7898c2485f475f20fd111efbf0f8`  
**Scope:** Stage B Specification Schema v0 and schema-only `example-001`  
**Runtime implementation:** Out of scope

## 1. Owner-ratified decisions

- Separate top-level `scope` field — RATIFIED.
- Reuse existing `hypothesis.py` and `prediction.py`; A2 compatibility verification is mandatory before freeze — RATIFIED.
- Separate top-level `evidence_classes` field — RATIFIED.
- `example-001` is one-run B2B API conformance for `Telegram webhook → JAMP Runtime → OpenRouter → Telegram response`, not an SLA/performance claim — RATIFIED.
- Incomplete/unverified execution is `UNKNOWN`; a proven contract violation is `FAIL`; conformance `PASS` requires all conditions and required evidence — RATIFIED.

## 2. A2 — Hypothesis / Prediction compatibility

### Observed in repository

`src/jamp/research/hypothesis.py` defines immutable `HypothesisRecord` with content hash `hypothesis_hash`. Its `export()` exposes `hypothesis_hash`; state transitions produce a new record/hash. This provides a candidate immutable target for N1 `hypothesis_ref`.

`src/jamp/research/prediction.py` defines immutable `PredictionRecord` with `hypothesis_ref`, `target_metric`, `expected_direction`, and `prediction_hash`. Its `export()` exposes the hash-bound payload. This provides a candidate immutable target for N1 `prediction_ref`.

### Gap found

The `ArtifactSource` Protocol now declares `get_hypothesis(ref)` and `get_prediction(ref)`, returning the immutable `HypothesisRecord` / `PredictionRecord` or `None`. `MappingArtifactSource` provides exact-key lookups and returns `None` for absent records.

`SpecificationGate.validate_a2_references()` verifies, in order:

1. Both references are lowercase SHA-256 values.
2. Both records resolve; absence or lookup failure emits `A2_UNRESOLVED`.
3. The resolved `hypothesis_hash` and `prediction_hash` equal their requested refs; mismatch emits `A2_HASH_MISMATCH`.
4. `prediction.hypothesis_ref` equals the Specification's `hypothesis_ref`; mismatch emits `A2_LINK_BROKEN`.

The Gate maps `A2_UNRESOLVED` to `GateStatus.UNKNOWN`; `A2_HASH_MISMATCH` and `A2_LINK_BROKEN` map to `GateStatus.FAIL`. This is a research Specification Gate change; it does not modify production runtime or the Frozen Core.

### A2 outcome

**IMPLEMENTATION: OBSERVED IN PR BRANCH.**  
**NEGATIVE TESTS: ADDED; CI VERIFICATION PENDING.**  
**A2 GATE: HOLD UNTIL TERMINAL CI.**

The contract test now checks the resolver surface, and dedicated Gate tests exercise unresolved Hypothesis, unresolved Prediction, hash mismatch, and broken Prediction→Hypothesis linkage. No A2 PASS is claimed before terminal CI evidence.

## 3. Canonicalization — JCS V1–V10

Current `src/jamp/research/canonical.py` uses Python `json.dumps` with sorted keys, compact separators, UTF-8 output, `ensure_ascii=False`, and rejects non-finite floats and non-string object keys.

This is observed deterministic serialization. It is **not evidence of RFC 8785 JCS conformance**.

Revised diagnostic harness added under `tests/research/canonical/`. Conformance/reference tests are opt-in via `JAMP_RUN_JCS_CONFORMANCE=1`; parser-boundary rejection tests run in the ordinary suite. The harness does not alter `canonical.py`.

| Vector | Required verification | Harness treatment | Outcome |
|---|---|---|---|
| V1 | `1.0` → `1` | Canonical-byte expected vector | NOT RUN |
| V2 | `1e21` → `1e+21` | Canonical-byte expected vector | NOT RUN |
| V3a | `9007199254740993` is outside the safe integer range | Strict parser rejects before hashing | TEST ADDED |
| V3b | `1e400` must not become Infinity | Strict parser rejects non-finite result | TEST ADDED |
| V4a | U+001F must be escaped | Valid escaped JSON input | NOT RUN |
| V4b | U+007F DEL remains literal | Printable-character vector | NOT RUN |
| V5 | Surrogate pair becomes U+1F600 | UTF-8 expected output | NOT RUN |
| V6 | UTF-16 code-unit key ordering | U+1F600 sorts before U+FB33 | NOT RUN |
| V7 | Duplicate JSON keys rejected | Strict `object_pairs_hook` | TEST ADDED |
| V8 | Whitespace omitted | Canonical-byte expected vector | NOT RUN |
| V9 | CR/LF string escapes preserved | Canonical-byte expected vector | NOT RUN |
| V10 | Canonicalization idempotence | Parse → canonicalize → parse → canonicalize | NOT RUN |
| REF | Independent `python-jcs` comparison | Optional reference + 100 Hypothesis examples | NOT RUN |

The opt-in tests are intentionally outside the default blocking suite while the serializer is known not to have established JCS conformance. The reference test skips if `jcs` or `hypothesis` is unavailable; a skip is not a pass.

**JCS status: OPEN / NOT VERIFIED.** Do not label `canonical.py` JCS-compliant and do not freeze hash semantics on this evidence. Record exact versions, command, exit status, and expected/actual bytes or hashes for any executed run.

## 4. Example-001 evidence boundary

The example is deliberately `SCHEMA_ONLY` with `reference_status=PENDING_FIRST_FULL_EVIDENCE_RUN` and `evidence_refs=TBD`.

A prior GitHub Actions run is recorded as **partial historical evidence only**:

- Run: `39561370652`
- Job: `119093183173`
- Artifact: `12328245109`
- Trace: `trace_78d81146`
- Requested and job-log-observed model ID: `minimax/minimax-m3.1-flash:free`
- Qualification: `NOT_GRANTED`

That run submitted a synthetic Telegram Update payload and did not capture all six Stage B evidence classes. It is not a full `example-001` conformance execution and cannot support PASS.

Required evidence classes:

1. `raw_webhook_payload` — original received bytes, including Telegram `update_id` and incoming `message_id`.
2. `jamp_runtime_log` — structured runtime events.
3. `provider_request_export` — exact OpenRouter request as sent.
4. `provider_response_export` — exact response as received, including headers and model metadata; preserve response snapshot/hash.
5. `telegram_send_result` — API status and outgoing Telegram `message_id`.
6. `execution_timing_export` — UTC start/end/key-step timestamps with explicit clock source.

Stage C Raw Evidence v0 must later bind concrete source records and `source_sha256`; Stage B only declares the required evidence classes.

## 5. Failure semantics boundary

The ratified `UNKNOWN` applies to the example/case status when execution or required evidence is incomplete. It is not a fabricated Classification or Verdict and must not produce a provenance-valid result.

A proven violation is `FAIL`. `PASS` requires every required evidence class, integrity verification, and every frozen one-run condition. This does not alter the frozen `PROVENANCE-CONTRACT-v0` requirement that classification/verdict derivation remain deterministic under frozen criteria and aggregation.

## 6. Remaining pre-freeze gates

- A2 exact reference resolution and compatibility tests: IMPLEMENTED IN PR; terminal CI verification pending.
- JCS V1–V10 plus independent implementation comparison: OPEN.
- Complete real `example-001` evidence run: PENDING.
- Q1–Q5 design proposals: remain PROPOSED; this package does not silently ratify them.
- Frozen Core `src/jamp/run.py`: expected blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`; branch read-back required before final review.

No runtime implementation or N1 freeze is included in this Stage B package.


## Status update — 2026-10-31

На основании ratification owner на main `4e7909ef`.

### A2 — VERIFIED

Evidence: PR #481, Run `41155212024`, Job `124400386151`, SUCCESS, 2147 passed.
Реализованы три кода отказа: `A2_UNRESOLVED`, `A2_HASH_MISMATCH`, `A2_LINK_BROKEN`.
`ArtifactSource.get_hypothesis/get_prediction` присутствуют в main.

### JCS — VERIFIED (per-run evidence)

Evidence: PR #482, Run `41169580036`, Job `124444420972`, SUCCESS, 2176 passed.
V1–V10 conformance + reference comparison против `jcs==0.2.1` пройдены.

Граница: этот статус относится к evidence конкретного прогона на `7e61ec9`
и merge `59a0e96`. Он не является вечным свойством реализации; переопределяется
evidence каждого нового прогона JCS harness.

### Q1–Q5 — RATIFIED

См. Addendum 2026-10-31 в `SPECIFICATION-SCHEMA-v0.md`. Q1–Q5 считаются
PROPOSED только в исторических записях ниже; ratified-решения superseding.

### N1 freeze vs Stage C

N1 freeze **не блокируется** полнотой example-001.
example-001 — Stage C gate. Текущий статус: `SCHEMA_ONLY`, `evidence_refs: TBD`.
Ни PASS, ни conformance claim не делается.

Исторические записи выше сохраняются как есть. Это дополнение их не переписывает.
