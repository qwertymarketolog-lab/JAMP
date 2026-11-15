# Experiment v3 — Live Claim Verification

**Status:** OPEN / DESIGN  
**Base:** 3ed79b90cf97a7a3b5710c62c04fb38b830bdbe0  
**Scope:** six files; workflow intentionally unchanged.

## Purpose

Verify one explicit user-supplied price claim through the existing deterministic claim extractor, adapter, and E4 provider. This is a research-only direct E4 path. It deliberately bypasses E2 generation verification and MUST NOT be represented as an E2-qualified generated answer.

## Request contract

POST /v1/verify_claim accepts only a text field and an optional tolerance_pct (default 1.0). The endpoint requires the existing API-key dependency. Exactly one extracted price claim is accepted. Missing ticker, numeric value, or currency; unsupported claim type; ambiguous multi-claim text; unknown provider mapping; and provider/network failures fail closed as INCONCLUSIVE.

## E4 tolerance

- API tolerance is expressed in percentage points (1.0 means 1%).
- MOEX receives fraction 0.01 through price_tolerance.
- CoinGecko receives percentage 1.0 through threshold_pct.
- Existing defaults and old call signatures remain unchanged when capture_raw=False.

## RAW Evidence binding

With capture_raw=True, each provider records bytes from the same HTTP response it parses:
- status_code
- body_complete
- raw_body_base64
- sha256_body
- request URL and source

MOEX records both catalog and market-data responses. CoinGecko capture mode bypasses its parsed-response cache so a captured network response is the one used for the verdict. The API independently decodes and re-hashes each captured body. A positive or negative E4 result without valid complete HTTP 200 RAW evidence is downgraded to INCONCLUSIVE.

No repeated evidence request and no global monkey-patching are used by the application.

## Modes

- --mock: deterministic offline HTTP fixtures; expected outcomes are VERIFIED, CONTRADICTED, INCONCLUSIVE. This proves code-path behavior only, not a live market fact.
- --live --confirm-live: makes bounded requests through the existing provider timeouts and writes the full response envelope. The first two verdicts are data-dependent; only the missing-currency case is deterministically INCONCLUSIVE.

## Invariants

- No call to verify_generation() from this endpoint.
- No changes to src/jamp/run.py (Frozen Core).
- No CI network calls; tests mock HTTP at the transport boundary.
- Existing /v1/execute and provider call contracts remain compatible.
- Workflow changes are out of scope for this PR.
