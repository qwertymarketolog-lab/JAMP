# Experiment v4 — AnyModel E2 → Extractor → E4

**State:** OPEN / DESIGN until live evidence is collected.
**Base SHA:** `b7ba1d67cfa291936db68ff7e7a58765926b8aef`.
**Frozen Core:** `src/jamp/run.py` must remain blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` (Δ=0).

## Purpose

Test one explicitly selected AnyModel model as E2 generator, preserve provider response evidence, reject known mock responses, and only then pass generated text to the deterministic claim extractor and external E4 verifiers.

This experiment does not qualify a model, prove general provider reliability, or turn one response into a benchmark PASS.

## Fixed model candidate

`ag/claude-sonnet-4-6`. This identifier is a candidate, not proof that the provider routed to that model.

## Stages and fail-closed contract

1. **Price attestation.** No AnyModel request is made unless an operator explicitly confirms price and supplies a non-empty pricing source plus a positive confirmed USD amount. This is manual attestation, not an independently verified tariff.
2. **E2 / AnyModel.** Exactly one request to the requested model. No provider fallback or silent model substitution.
3. **RAW capture.** Preserve all response headers exposed by urllib, the complete response body, body SHA-256, and a reconstructed HTTP representation (headers + body) with SHA-256. This is not a packet-level wire capture. Request Authorization headers are not stored.
4. **Preflight.** Refuse known mock signatures (`chatcmpl-abc123`, response model `openai/gpt-5` / `gpt-5`, or `Hi! I'm an AI assistant`). Refuse `MODEL_MISMATCH` unless provider-reported model exactly equals requested model. Missing model or content also refuses.
5. **Extractor.** Only after preflight succeeds, call `extract_claims`. Ambiguous, multiple, or unsupported claims remain `INCONCLUSIVE`.
6. **E4.** Only when `--full-cycle` is explicitly requested after successful preflight, verify supported price claims against MOEX (RUB) or CoinGecko (USD). E4 network failure or missing/invalid RAW evidence cannot produce VERIFIED or CONTRADICTED.

## Modes

- `--mock`: deterministic, network-free mock scenarios; used by PR CI.
- `--live --confirm-live`: one live AnyModel request, only after manual price attestation. Default is probe-only and does not call E4.
- `--live --confirm-live --full-cycle`: after successful preflight, run extractor and E4.
- Dedicated GitHub workflow is `workflow_dispatch` only. Both `confirm_live_requests` and `confirm_price` must be true, with source and amount supplied, before the live request.

## Verdict semantics

- `REFUSE`: a safety/preflight gate prevented downstream processing.
- `OBSERVED`: provider response passed configured preflight checks. This does not prove authenticity beyond tested signatures or qualify the model.
- `VERIFIED` / `CONTRADICTED` / `INCONCLUSIVE`: E4 result only, subject to valid captured external RAW evidence.

## CI and non-actions

PR CI runs mock-only tests. It must not receive or use `ANYMODEL_API_KEY`, must not contact AnyModel, MOEX, or CoinGecko, and must not incur model charges. No live probe is authorized by this PR. No provider priority changes are made. Frozen Core remains untouched.

## Evidence required after merge

A separately authorized workflow run, terminal job result, and uploaded artifact containing `evidence.json` plus `anymodel_raw_http.bin`. Live execution remains HOLD until price source and amount are explicitly confirmed by the operator.
