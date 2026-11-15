# Experiment v2 — Live API Record & Replay

**Status:** DESIGN APPROVED; live execution remains separately gated.  
**Experiment ID:** JAMP-E4-LIVE-RECORD-REPLAY-V2

## 1. Objective and evidence boundary

Capture exactly one bounded HTTP response from each public source:

- MOEX SBER ISS: `https://iss.moex.com/iss/engines/stock/markets/shares/securities/SBER.json?iss.meta=off`
- CoinGecko BTC: `https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd`

This experiment proves only that JAMP can acquire, preserve, hash, and parse the captured responses. It does **not** establish that an arbitrary claim is true. No user claim is supplied to this acquisition experiment; therefore every derived `jamp_verdict` is `INCONCLUSIVE` with reason `NO_CLAIM_CONTEXT`. A parsed market value is an observation, not a qualification or PASS.

## 2. Execution model

- The live workflow is triggered only by `workflow_dispatch`.
- The explicit boolean input `confirm_live_requests` defaults to false. Without it, the runner refuses to make requests.
- Exactly one sequential GET per source; no retries, no polling, no parallel requests, no API keys, no paid endpoints.
- Timeout: 5 seconds per request. Maximum captured body: 1 MiB per source.
- HTTPS and exact source host/path allowlist only. Redirects are not followed.
- Network errors and HTTP errors are recorded as evidence. They are not silently converted into success.
- The workflow uploads its artifact with `if: always()`, including when a request fails.
- Pull-request CI makes no network requests. Unit tests use explicitly labelled test-only byte fixtures.
- Real response fixtures may be committed later under `tests/research/fixtures/live/` after review. Only then can PR-CI replay those real captured bytes. A workflow artifact by itself is not silently treated as a committed replay fixture.

## 3. RAW Evidence contract

One immutable acquisition record per source is written as `<source>.raw.json`; the exact captured bytes are written as `<source>.body`.

Schema identifier: `jamp.raw-http-evidence.v1`.

Required fields:

| Field | Meaning |
|---|---|
| `schema` | Exact schema identifier |
| `source` | `MOEX` or `CoinGecko` |
| `url` | Exact requested URL |
| `timestamp_utc` | UTC request-start timestamp |
| `captured_at_utc` | UTC capture-completion timestamp |
| `status_code` | HTTP status, or null if no HTTP response was received |
| `response_headers` | Allowlisted non-secret response headers only |
| `body_file` | Relative path to the captured body bytes |
| `body_complete` | False if the configured size cap was exceeded |
| `sha256_body` | SHA-256 of the exact bytes stored in `body_file` |
| `raw_body_base64` | Base64 representation of the exact captured bytes |
| `raw_body` | UTF-8 text when strict UTF-8 decoding succeeds; otherwise null |
| `error_type`, `error_message` | Bounded transport/HTTP error description, or null |

The hash is computed from original response bytes before decoding or parsing. If the size cap is exceeded, the partial capture is explicitly marked `body_complete=false`; its hash is only the hash of captured bytes and must not be represented as the hash of the complete upstream response.

RAW records and body files contain acquisition facts only. They MUST NOT contain `parsed_value`, `jamp_verdict`, or other derived interpretations.

## 4. Derived result contract

A separate `experiment_v2_result.json` contains, per source:

- `raw_record_sha256`: SHA-256 of the serialized raw-record file;
- `body_sha256_verified`: whether the saved body matches `sha256_body`;
- `parsed_value`: a positive finite numeric MOEX `marketdata.LAST` or CoinGecko `bitcoin.usd`, otherwise null;
- `parse_status`: `PARSED` or `INCONCLUSIVE`;
- `jamp_verdict`: always `INCONCLUSIVE` for this no-claim acquisition experiment;
- `reason`: explicit reason, including HTTP failure, missing field, invalid JSON, incomplete body, or `NO_CLAIM_CONTEXT`.

The top-level experiment status is `OBSERVED` only when both sources return HTTP 200 and both values parse. Otherwise it is `INCONCLUSIVE`. Neither status is a claim-verification PASS.

## 5. Failure handling

- DNS/TLS/connection/timeout failure: status_code null, empty body file, explicit error fields, derived INCONCLUSIVE.
- HTTP 4xx/5xx including 429: preserve status, response headers, and response body; derived INCONCLUSIVE.
- Invalid JSON, missing expected table/value, non-positive or non-finite value: derived INCONCLUSIVE.
- Body larger than 1 MiB: preserve the bounded captured prefix, mark incomplete, and refuse parsing.
- Missing replay file or SHA mismatch: refuse to derive a value from it.
- No failure path may synthesize a price, `VERIFIED`, `QUALIFIED`, or PASS.

## 6. Frozen Core and scope

Only these five files are in scope for PR 5:

1. `docs/experiments/jamp_audit_v1/experiment_v2_spec.md`
2. `scripts/research/evidence_http.py`
3. `scripts/research/run_experiment_v2.py`
4. `tests/research/test_experiment_v2.py`
5. `.github/workflows/experiment-v2-live.yml`

The existing application/provider transport uses Python's standard-library `urllib.request`; there is no `src/jamp/core/` package. This experiment uses a thin research-only wrapper and does not change production transport or provider modules.

Frozen Core `src/jamp/run.py` must remain byte-identical at blob SHA `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` (Δ=0).
