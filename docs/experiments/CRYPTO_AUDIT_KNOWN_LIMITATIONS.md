# Crypto Audit v1 — Known Limitations

## E2 Generation API: repeated HTTP 404 before success

**Observed:** In Crypto Audit v1 Run `40663556169` on SHA `f344ec6bb6de6209f2a930c00d94f3ef7b18f5b5`, the E2 Generation API lookup returned HTTP 404 on attempts 1–3 and HTTP 200 on attempt 4 for both C02 (ETH) and C03 (SOL).

| Trace | Attempts (HTTP status) | Successful attempt |
|---|---|---|
| `trace_0ae85262` (C02 ETH) | 404, 404, 404, 200 | 4th |
| `trace_0d3e9b46` (C03 SOL) | 404, 404, 404, 200 | 4th |

**Evidence:** Run `40663556169`, Job `122732283459`, artifact `crypto-audit-v1-report` (ID `12804104107`). The artifact SHA-256 is `be08c03b60427b04918a5ca02c4a9bd2cf5ea80364533066ea8c840cb3f5b76e`.

**Configured mitigation:** `src/jamp/provider/e2_verify.py` defines `NOT_FOUND_BACKOFF_SECONDS = (1, 2, 4, 8, 16)` and calls `time.sleep(delay)` after each retryable HTTP 404. The observed fourth-attempt successes are consistent with this retry policy.

**Cause — not independently established:** Asynchronous indexing/availability of new OpenRouter generations is a plausible explanation for the 404-then-200 pattern, but this run does not independently prove the provider-side cause. The job log and provenance artifact do not contain per-attempt wall-clock timestamps, so actual sleep intervals cannot be verified from this run's logs alone. The `elapsed_ms` fields measure individual HTTP attempts, not the sleep between them.

**Current behavior and limits:**
- For C02 and C03, the fourth request succeeded after three 404 responses.
- The configured delays total 31 seconds across five retry sleeps (1 + 2 + 4 + 8 + 16). The implementation can make a sixth request after those sleeps; if that request also returns 404, the lookup returns `INCONCLUSIVE`.
- Runs with repeated 404s can incur additional latency. Monitor `E2_VERIFICATION_INCONCLUSIVE` and attempt counts in future runs.

**What this is not evidence of:**
- It is not evidence of a general OpenRouter outage: C02 and C03 both received HTTP 200 on a later attempt.
- It is not proof that provider-side indexing lag is the sole cause.
- The Crypto Audit v1 run itself was not fully successful: 11 of 12 cases passed; C01 failed because the harness expected `EXECUTE` but the actual result was `REFUSE` after E4 returned `CLAIM_LEVEL_CONTRADICTION`.

## C01 (BTC): no E2 attempts

C01 trace `trace_d7fb8287` was refused at E4 with `CLAIM_LEVEL_CONTRADICTION` before `verify_generation` was called. The claim was $67,200 while the observed CoinGecko value was $81,425 (relative delta 17.47%). Therefore no E2 HTTP attempts occurred; `attempts=null` is consistent with this pre-E2 refusal path and should not be rewritten as `attempts=[]` merely to imply an E2 call occurred.

## Do not change without new evidence

- Do not change `NOT_FOUND_BACKOFF_SECONDS` unless evidence shows the current policy is insufficient.
- Do not change `attempts=null` for an E4 refusal that occurs before E2 is called.
- Do not claim that the actual wall-clock backoff intervals were measured from this run; they were not.
