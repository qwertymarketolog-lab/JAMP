# ADR: API key authentication v0 (PR-2 skeleton)

- **Status:** Proposed; draft PR only.
- **Base:** `main` at `f5b470afbaa36014daa021a5a3493fe1e53b83bd`.
- **Frozen Core:** `src/jamp/run.py` Git blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`; must remain unchanged.

## Context

The database foundation stores one unique `organizations.api_key_hash` per organization. PR-2 proposes API-key authentication for the existing public v1 API routes without changing the Telegram webhook security boundary.

## Decision A — key cardinality and rotation

MVP stores one API key per organization using the existing `organizations.api_key_hash UNIQUE` column. Multi-key support and in-place rotation are out of scope. Rotation is an explicit downtime operation and requires a follow-up issue; no issue number is assigned until that issue exists.

## Decision B — token generation, storage, and verification

- Generate a token with `secrets.token_urlsafe(32)` (32 random bytes; 256 bits of entropy before URL-safe encoding).
- Store only `HMAC-SHA256(JAMP_API_KEY_HASH_SECRET, token)`; never store or log the plaintext token.
- Verify with `hmac.compare_digest`.
- Missing `JAMP_API_KEY_HASH_SECRET` is a fail-closed configuration error. Do not silently fall back to plain SHA-256 or another key.
- **Why HMAC-SHA256 rather than bcrypt/Argon2:** these are password-hashing KDFs intended to slow guessing of low-entropy human secrets. A 256-bit randomly generated API token is not realistically brute-forceable; a keyed HMAC supports deterministic equality lookup through the existing unique index and avoids a per-request slow KDF. Keeping the HMAC secret separate from the database also prevents a database-only leak from being sufficient to validate guesses. Secret storage/rotation policy remains an operational concern.
- This ADR is a proposal pending implementation and review; it does not claim runtime behavior is implemented.

## Decision C — HTTP error model

| Condition | Response |
|---|---:|
| Missing or invalid API key | 401 |
| Valid key belonging to a disabled organization | 403 |
| Database unavailable | 503 |

The protected handler must not execute for any of these failure paths. Database errors must not be misreported as 401. Responses and logs must not disclose the key or its digest.

## Scope boundary — Telegram isolation

Authentication is attached **per-router or per-route** to `/v1/classify`, `/v1/execute`, `/v1/provenance/{trace_id}`, and `/v1/verify-verdict`. A global middleware or app-wide dependency is prohibited in PR-2. The Telegram webhook remains on its separate `X-Telegram-Bot-Api-Secret-Token` authentication path and must not be routed through API-key auth.

## Test plan

- [ ] Unit: missing key → 401; wrong key → 401; valid key; valid key + disabled organization → 403.
- [ ] Unit: missing HMAC secret fails closed; API key never appears in logs.
- [ ] Unit/API: database unavailable → 503, not 401.
- [ ] API: mock/spy proves protected handlers are not called on 401/403/503.
- [ ] PostgreSQL / Run Pytest: digest lookup, disabled organization, and cross-organization isolation.
- [ ] Regression: Telegram webhook continues to work with its own secret; mandatory before merge.
- [ ] CI Frozen Core guard verifies `src/jamp/run.py` blob remains `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

## Out of scope

Key rotation implementation, multiple keys per organization, scopes/claims, rate limiting, OAuth, changes to `src/jamp/run.py`, and changes to `src/jamp/db/connection.py`.

## Definition of done for moving this draft to Ready for review

- [ ] `auth.py` plus per-router/per-route wiring implemented.
- [ ] Local unit tests pass.
- [ ] Run Pytest PostgreSQL integration tests pass on GitHub Actions.
- [ ] Telegram regression passes.
- [ ] A/B/C decisions are reflected in the PR description and this ADR.
- [ ] Frozen Core blob matches the locked value.
- [ ] Both required CI workflows have terminal successful conclusions.

Until all criteria are supported by evidence and reviewed, this PR remains draft and must not be merged.
