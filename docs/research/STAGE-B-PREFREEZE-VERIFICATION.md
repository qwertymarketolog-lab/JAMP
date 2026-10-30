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

The current `ArtifactSource` Protocol in `src/jamp/research/specification_gate.py` exposes resolution methods for Specification, Criterion Set, Criterion, and Aggregation Rule only. It has no `get_hypothesis` or `get_prediction` resolver.

The current Specification validation checks required-field presence and the declared Specification hash, but does not independently validate the Hypothesis/Prediction hash format or resolve those two references to the exact records.

### A2 outcome

**STRUCTURAL MAPPING: OBSERVED / COMPATIBLE IN PRINCIPLE.**  
**END-TO-END REFERENCE INTEGRITY: NOT VERIFIED.**  
**A2 GATE: HOLD.**

A2 cannot pass on dataclass shape alone. Before N1 freeze, the resolver contract and tests must prove that both references resolve to exact immutable records and that the resolved record hashes match the N1 references. This package adds a RED contract test for the missing resolver surface; it does not implement runtime behavior.

## 3. Canonicalization — JCS V1–V10

Current `src/jamp/research/canonical.py` uses Python `json.dumps` with sorted keys, compact separators, UTF-8 output, `ensure_ascii=False`, and rejects non-finite floats and non-string object keys.

This is observed deterministic serialization. It is **not evidence of RFC 8785 JCS conformance**.

| Vector | Required verification | Outcome |
|---|---|---|
| V1 | `1.0` versus `1` number normalization | NOT RUN |
| V2 | `1e21` ECMAScript/JCS number formatting | NOT RUN |
| V3 | `9007199254740993` precision-loss handling | NOT RUN |
| V4 | Actual control characters versus printable U+007F/U+0080 | NOT RUN |
| V5 | Valid surrogate-pair handling | NOT RUN |
| V6 | UTF-16 code-unit object-key ordering | NOT RUN |
| V7 | Duplicate JSON-key rejection at parse boundary | NOT RUN |
| V8 | Whitespace/newline invariance after parsing | NOT RUN |
| V9 | Cross-implementation canonical-byte/hash equality | NOT RUN |
| V10 | Canonicalization idempotence | NOT RUN |

**JCS status: OPEN / NOT VERIFIED.** Do not label `canonical.py` JCS-compliant and do not freeze hash semantics on this evidence. Any future result must record the exact vectors, implementation(s), command, exit status, and expected/actual bytes or hashes.

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

- A2 exact reference resolution and compatibility tests: OPEN.
- JCS V1–V10 plus independent implementation comparison: OPEN.
- Complete real `example-001` evidence run: PENDING.
- Q1–Q5 design proposals: remain PROPOSED; this package does not silently ratify them.
- Frozen Core `src/jamp/run.py`: expected blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`; branch read-back required before final review.

No runtime implementation or N1 freeze is included in this Stage B package.
