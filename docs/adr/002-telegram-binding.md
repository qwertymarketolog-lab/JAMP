# ADR P31.2 — Trusted Telegram Chat Binding to Organization

**Project:** JAMP  
**ADR:** 002  
**Status:** APPROVED (CONCEPT ONLY) / IMPLEMENTATION HOLD  
**Date:** 2026-11-16  
**Baseline main:** `f84f97a79ec760109e33340f9838323a767141fb`  
**Scope:** Telegram ingress → trusted tenant identity → shared Runtime  
**Related decision:** JAMP-DEC-001 — Tenant Isolation (remains HOLD)  
**Frozen Core:** `src/jamp/run.py`, locked blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`; required delta `0`.

> This ADR records an approved architectural concept. It does not authorize implementation. User identity/roles, migration strategy, and the shared Runtime service contract remain blocking prerequisites.

## 1. Context and problem

The active `POST /v1/telegram/webhook` validates `TELEGRAM_WEBHOOK_SECRET`, checks one configured `TELEGRAM_CHAT_ID`, and validates `update_id`. It deliberately refuses executable commands with `ORGANIZATION_CONTEXT_REQUIRED`.

The ordinary API path obtains `OrganizationContext` through `require_api_key`: a Bearer API key is HMAC-hashed, looked up against `organizations.api_key_hash`, and rejected if unknown or disabled.

The current Dashboard adds a signed, one-hour browser cookie. However, login still exchanges an organization API key for a session containing only `org_id`; it does not establish a human `user_id`, role, or membership. `require_api_key` accepts this cookie only for GET/HEAD. The separate UI BFF POST route has Origin and session-bound CSRF checks, but it does not create a user/role authorization model.

Therefore:
- webhook secret authenticates the configured webhook source; it does not identify a tenant;
- a single `TELEGRAM_CHAT_ID` is an allowlist, not a multi-tenant binding;
- `organization_id` supplied by Telegram is not an authorization credential;
- a shared organization API key in Telegram is prohibited;
- current Dashboard session is not proof that its holder is an organization owner/admin;
- executable Telegram commands must remain fail-closed until a trusted binding and authorized owner workflow exist.

## 2. Decision

Adopt the following target concept:

`Telegram private chat → server-side active binding → OrganizationContext → shared Runtime service`

A binding is created only after two independent proofs:

1. An authorized organization user initiates the operation in an authenticated Dashboard.
2. The Telegram private chat submits a short-lived one-time challenge; the resulting pending claim is explicitly approved in the Dashboard by an authorized organization user.

The challenge proves control of the Telegram chat. Dashboard approval proves the organization’s intent to associate that chat with the organization. Neither proof alone activates the binding.

**Concept approval is not implementation approval.** Implementation remains blocked by Section 9.

## 3. Security invariants

1. Tenant identity is never derived from `organization_id` in Telegram update, command text, or client JSON.
2. The organization is selected only from a verified server-side principal when creating a challenge.
3. API keys and bot tokens are never sent to Telegram or stored in binding records.
4. Unknown, expired, revoked, disabled, duplicate, or ambiguous bindings refuse before Runtime.
5. Runtime receives a server-constructed `OrganizationContext`, not a caller-supplied org identifier.
6. Organization disabled state is checked against current authoritative storage before execution.
7. Duplicate updates cannot execute Runtime twice.
8. Delivery success is recorded only after a valid Telegram Bot API response with `ok: true`.
9. Delivery retries reuse the recorded Runtime result; they do not repeat Runtime execution.
10. No secret, API key, bot token, or raw challenge is written to logs or artifacts.
11. Frozen Core remains unchanged: `src/jamp/run.py` blob must remain exactly `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
12. Telegram binding does not close or supersede JAMP-DEC-001.

## 4. Identity and double-confirmation challenge flow

### 4.1 Owner initiation in Dashboard

1. A human user authenticates to the JAMP Dashboard.
2. The backend resolves a verified user identity and organization membership.
3. The backend checks an explicit permission such as `telegram_binding:create`.
4. The organization ID is taken only from the server-side authenticated membership/context.
5. The server generates a cryptographically random challenge with at least 256 bits of entropy.
6. Only a hash of the challenge is persisted, together with organization, creator, creation time, expiry, and state.
7. The raw challenge is returned once to the authorized Dashboard user.

**Current gap:** Dashboard login presently authenticates an organization API key and issues a stateless signed cookie with `org_id`; there is no observed `User`, `user_id`, `owner`/ `admin` role, or organization-membership authorization in the inspected path. Any implementation must first establish human identity and permissions. An API key must not be treated as proof of an individual owner/admin role.

### 4.2 Claim from Telegram

1. The user opens a private chat with the official JAMP bot.
2. The user sends `/start <one-time-token>`.
3. The active webhook validates the Telegram secret header, update structure, private-chat type, and challenge.
4. The server atomically consumes the challenge once and creates a short-lived `CLAIMED` request containing the bot/chat identifiers and the organization from the challenge record.
5. The binding remains inactive.
6. An authorized user for that same organization reviews the pending claim in Dashboard and explicitly approves it.
7. The server atomically creates the active binding and records who approved it.

A stolen challenge can at most create a pending claim; it cannot activate a binding without Dashboard authorization. Challenge values must not be placed in URLs, analytics, or logs.

Telegram username and display name are informational only. The security identifiers are Telegram numeric IDs. Version 1 supports private chats only; group chats are out of scope.

### 4.3 Authorization and revocation

The implementation must introduce or reuse a real human-user and organization-membership model with explicit permissions. At minimum, create and approve require an authorized organization owner/admin. The exact role names, bootstrap/invitation process, recovery, and multi-admin behavior are unresolved and must be designed before implementation.

Revocation is a separate authenticated action. It revokes only the selected binding and must be audited. Organization disablement blocks all its bindings immediately.

## 5. Session lifetime and logout

Keep three concepts separate:

- **Challenge:** one-time, short-lived authorization to create a pending claim.
- **Telegram binding:** durable association until explicit revocation or organization disablement.
- **Dashboard session:** browser authentication, governed by the Dashboard session policy.

Proposed challenge lifetime: 10 minutes. A claimed-but-unapproved request expires after 10 minutes. Expired challenges and claims cannot be approved.

Dashboard logout does not automatically revoke an active Telegram binding. It clears the browser session only. Revocation is explicit and separately authorized.

**Observed implementation caveat:** current Dashboard sessions are signed and expire after one hour; the session payload contains `org_id` and `exp`, not a user identity. The current logout clears cookies client-side; no server-side session revocation store was observed. Do not reuse this session as the final owner/admin authorization contract without a security design for user identity, role checks, CSRF, and session revocation.

## 6. Transport

**Decision:** HTTPS Webhooks only for version 1.

Requirements:
- public HTTPS endpoint;
- validate `X-Telegram-Bot-Api-Secret-Token` with constant-time comparison;
- validate update structure and accept only supported private-chat message types;
- bound request body size and processing time;
- do not log secrets or challenge values;
- do not run Long Polling for the same bot as a fallback.

The current active FastAPI webhook is the integration point. A separate unused router or adapter is not a substitute for wiring the registered `create_app()` endpoint.

If webhook ingress is unavailable, Telegram execution is unavailable. No security check is bypassed to restore service.

## 7. Rate limiting and abuse controls

Apply limits at multiple boundaries:

**Before tenant resolution**
- malformed/unauthenticated webhook request limits;
- challenge-attempt limits by challenge hash;
- per-source limits only where source IP is trustworthy;
- limits on outstanding challenges per organization;
- body-size and command-length limits.

**After tenant resolution**
- per-organization request and concurrency quotas;
- per-chat request limits;
- Runtime resource quotas consistent with the existing Runtime policy.

Counters must be durable/atomic for multi-worker operation. An in-memory-only counter is insufficient. Exact numeric thresholds remain an operational decision and must be measured/approved; this ADR does not invent them. Exceeding a limit must prevent Runtime invocation.

## 8. Anti-CSRF and anti-replay

- Challenge creation and claim approval require authenticated, role-authorized Dashboard operations.
- Browser POST operations require Origin validation and session-bound CSRF protection.
- Challenge has at least 256 bits of entropy, a 10-minute TTL, hashed-at-rest storage, attempt limits, and atomic single-use consumption.
- A claim is not active until explicitly approved in Dashboard.
- Telegram update idempotency must be durable and scoped by bot identity plus `update_id`.
- Concurrent duplicate deliveries must result in one execution owner.
- Delivery retries must reuse persisted results.
- Raw challenges, API keys, bot tokens, and session secrets must be redacted from logs and artifacts.

CSRF protection for browser operations and replay protection for Telegram updates are distinct controls; neither substitutes for the other.

## 9. Tenant isolation and Runtime call path — P0 blockers

### 9.1 Trusted tenant resolution

For each executable Telegram update:

`verified webhook → validated private chat → unique active binding lookup → current organization-state check → OrganizationContext → Runtime`

The binding lookup must identify exactly one active organization for the tuple `(bot_id, chat_id)`. Missing, disabled, revoked, expired, or ambiguous state refuses before Runtime.

A chat may not be bound to multiple organizations for the same bot. An organization may have multiple private chats, each represented by a separate binding.

### 9.2 Shared in-process Runtime service

**Decision:** use one shared tenant-scoped application service, called in-process by both the HTTP route and Telegram webhook.

Target interface (conceptual, not implemented):

`execute(payload, organization: OrganizationContext) -> RuntimeResult`

The HTTP route obtains `OrganizationContext` from `require_api_key` and calls the service. Telegram obtains it from the trusted binding resolver and calls the same service. Both paths must execute identical business logic, persistence scoping, refusal rules, and trace handling.

Do not:
- call `/v1/execute` through an unauthenticated HTTP adapter;
- pass a global API key;
- store plaintext organization API keys;
- trust client-supplied `org_id`;
- duplicate Runtime business logic in the Telegram handler.

**Current gap:** `/v1/execute` currently contains execution logic inside its FastAPI handler. The inspected `JampClientAdapter` calls the HTTP endpoint without an Authorization header. A reusable service boundary has not been verified. Extracting that service is a P0 prerequisite and must preserve the existing HTTP contract.

### 9.3 DEC-001 boundary

JAMP-DEC-001 remains HOLD. The Telegram feature must not be presented as proof of general tenant isolation. Existing cross-organization data access and persistence scoping must be qualified separately. Telegram-specific tests can prove only the Telegram path and controls they actually exercise.

## 10. Persistence and migrations

**Observed PostgreSQL foundation:**
- `organizations`, `audit_traces`, `verdicts`, and `evidence_chain` are defined in `src/jamp/db/schema.sql`;
- `src/jamp/db/init.py` applies the schema through `init_schema()`;
- database access uses the PostgreSQL connection pool in `src/jamp/db/connection.py`.

**Observed migration gap:** the inspected `main` tree contains no Alembic configuration, migration environment, or migration versions; Alembic is not listed in `pyproject.toml`. The current bootstrap schema is not a versioned migration history.

Before adding binding/challenge tables, choose and establish a controlled schema migration mechanism. Alembic is the proposed option, subject to a separate implementation plan for baseline adoption, existing installations, rollback/forward-fix policy, and CI validation. Do not assume that simply adding Alembic files safely migrates already-provisioned databases.

Proposed logical records:

- `telegram_binding_challenges`: organization, token hash, status, created/expiry/claimed timestamps, attempt count, creator.
- `telegram_binding_claims`: challenge, organization, bot/chat/user numeric IDs, pending/approved/expired/rejected state, approver and timestamps.
- `telegram_bindings`: organization, bot/chat/user IDs, active/revoked state, creator and revocation audit.
- `telegram_updates`: bot ID, update ID, binding, processing state, trace ID, timestamps.
- `telegram_deliveries`: update/result reference, delivery state, attempts, last error and delivered timestamp.

This is a logical model, not an approved SQL schema. Required database constraints include:
- unique active `(bot_id, chat_id)`;
- unique `(bot_id, update_id)`;
- foreign keys to organizations and related records;
- atomic challenge consumption and binding activation;
- indexes supporting binding lookup and update idempotency;
- durable result/delivery state.

**Existing idempotency caveat:** `src/jamp/transport/telegram_updates.py` currently uses a SQLite table with `update_id` as its primary key and an atomic claim operation. It is not the proposed PostgreSQL binding/update/delivery model, is not scoped by `bot_id`, and does not represent the complete processing/delivery lifecycle. It must not be treated as satisfying the new persistence contract.

## 11. Delivery and failure behavior

Runtime result and Telegram delivery state are separate.

Target processing states:

`RECEIVED → CLAIMED → RUNTIME_STARTED → RESULT_RECORDED → DELIVERY_PENDING → DELIVERED`

Other states include `REFUSED`, `RATE_LIMITED`, `DELIVERY_FAILED`, `AMBIGUOUS`, and `RECONCILIATION_REQUIRED`.

If Runtime is unavailable, return a truthful message such as:

> Проверка временно недоступна. Запрос не подтверждён. Попробуйте позже.

A Runtime `REFUSE` must preserve its original reason and trace ID. It must not be represented as success.

If Telegram Bot API returns timeout, malformed JSON, `ok: false`, or another error:
- delivery is not marked successful;
- the Runtime result remains persisted;
- a retry reuses the recorded result and does not execute Runtime again;
- reconciliation records unresolved delivery.

Do not claim exactly-once delivery to an external Telegram API without evidence. The required guarantee is no duplicate Runtime execution for the same accepted update, with durable, auditable delivery recovery.

## 12. Threat model

| Threat | Required control | Residual risk |
|---|---|---|
| Forged tenant ID | Ignore client `organization_id`; resolve server-side binding | Resolver implementation defect |
| Stolen challenge | High entropy, TTL, hash, single use, Dashboard approval | Compromised authorized Dashboard session |
| Unauthorized binding approval | Human identity, org membership, explicit role/permission | Account takeover |
| Webhook spoofing | HTTPS and Telegram secret header | Secret compromise |
| Cross-tenant access | Unique binding and explicit OrganizationContext in shared Runtime | Runtime data-scope defect |
| Replay/race | Unique update key and atomic state transitions | Transaction boundary defect |
| Abuse/spam | Durable rate limits and quotas | Distributed abuse |
| Organization disablement | Current status check before execution | In-flight revocation race |
| Delivery failure | Separate durable result and delivery states | Telegram outage |
| Credential leakage | Hashing, redaction, no credentials in Telegram | Logging/configuration defect |

## 13. Required qualification tests

The following are required acceptance scenarios; listing them is not evidence that tests exist or have passed.

1. Challenge creation uses only the organization from the authenticated user membership.
2. A user without integration-management permission cannot create, approve, or revoke a binding.
3. A valid `/start <token>` creates only a pending claim.
4. An unapproved claim cannot invoke Runtime.
5. Dashboard approval activates exactly one binding.
6. Invalid, expired, consumed, and brute-forced challenges are refused.
7. Client-supplied `organization_id` cannot influence tenant selection.
8. Chat A cannot obtain Organization B context.
9. Disabled organizations are refused before Runtime.
10. Revoked bindings are refused before Runtime.
11. Missing, duplicate, or ambiguous bindings are refused before Runtime.
12. Missing/invalid Dashboard credentials are refused.
13. Duplicate `update_id` does not invoke Runtime twice.
14. Concurrent duplicate updates have one execution owner.
15. Runtime EXECUTE preserves trace and result.
16. Runtime REFUSE preserves original reason and trace.
17. Telegram `ok: false`, timeout, and malformed JSON are not successful delivery.
18. Failure after Runtime result persistence does not repeat Runtime on retry.
19. Binding, update, and delivery state survive restart.
20. API keys, bot token, session secret, and challenge do not appear in logs/artifacts.
21. Frozen Core blob remains exact.
22. DEC-001 is separately evaluated and is not closed by Telegram-specific tests.

Tests must exercise the active `create_app()` endpoint, real auth and persistence wiring, and the shared Runtime service. Isolated mocks may supplement but cannot replace these integration tests.

## 14. Open prerequisites before implementation

| ID | Prerequisite | Current status | Required resolution |
|---|---|---|---|
| P0-1 | Human User / Organization Membership / owner-admin permissions | UNKNOWN / HOLD | Design identity, membership, role, bootstrap, recovery, and permission checks. Existing API-key Dashboard session is insufficient. |
| P0-2 | Dashboard write-session authorization | HOLD | Define role-authorized POST flow, CSRF/Origin, session expiry and revocation. Current `require_api_key` cookie path is GET/HEAD only. |
| P0-3 | Versioned PostgreSQL migrations | HOLD | Select migration mechanism (proposed Alembic), baseline existing schema, define rollout/rollback and CI checks. |
| P0-4 | Shared Runtime service | HOLD | Extract common in-process service accepting explicit `OrganizationContext`; route HTTP and Telegram through it. |
| P0-5 | Durable Telegram binding/update/delivery store | HOLD | Approve schema, unique constraints, transaction boundaries, retention and recovery. Existing SQLite claim store is insufficient. |
| P0-6 | DEC-001 | HOLD | Independently qualify cross-organization read/write isolation; do not infer closure from P31.2. |
| P0-7 | Rate limits and operational policy | UNKNOWN | Define measured limits, retry policy, monitoring, and retention. |

No implementation may begin while any P0 prerequisite affecting authorization, tenant selection, persistence, or Runtime remains unresolved.

## 15. Definition of Done

### Architecture gate
- Human identity and organization-role model approved.
- Binding challenge, claim approval, revocation, and conflict semantics approved.
- Migration strategy and baseline adoption approved.
- Shared Runtime service contract approved.
- Persistence and delivery state model approved.
- DEC-001 dependency and non-claims documented.

### Implementation qualification gate
- All required security/integration scenarios have actual results.
- EXECUTE and REFUSE are tested through active webhook and shared service.
- Replay, race, restart, disablement, revocation, and delivery recovery are tested.
- Database migration is tested from the existing baseline.
- Frozen Core blob remains exact.
- GitHub Actions terminal Run → Job → Conclusion → Artifact evidence is available for applicable claims on the exact SHA.
- Post-merge CI on main is checked separately after an explicitly authorized merge.

## 16. Current state and authority

- **P31.2 concept:** APPROVED.
- **ADR record:** this document records the approved concept and unresolved prerequisites.
- **Implementation:** HOLD.
- **Telegram executable commands:** remain fail-closed.
- **PR for implementation:** not authorized.
- **Frozen Core:** locked; required delta zero.
- **JAMP-DEC-001:** HOLD.

This ADR authorizes documentation of the concept only. It does not authorize code changes, database migrations, secret changes, deployment, or merge.

**Principle: Proof over confidence. Approve the contract first; implement only after blockers are resolved; qualify with evidence.**
