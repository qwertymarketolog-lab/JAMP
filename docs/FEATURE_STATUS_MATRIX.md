# JAMP — Feature Status Matrix

> Historical comparison snapshot. This document records code observations at two immutable Git revisions; it is not a live deployment or CI qualification report.

## Audit coordinates

| Item | Revision / value | Evidence level |
|---|---|---|
| Historical baseline | `4a1daebdb3abd94952c87cdab306ba02acb54660` (2026-11-05) | OBSERVED |
| Comparison target | `0aadb070a7ddc9d59806ad5cfe95eda336c5aa66` (`main`) | OBSERVED |
| Frozen Core path | `src/jamp/run.py` | OBSERVED |
| Frozen Core expected blob | `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` | VERIFIED by prior `git ls-tree` evidence recorded for this audit |
| Frozen Core delta | `0` | VERIFIED for comparison target |

**Scope:** read-only source inspection. Route registration was inspected in `src/jamp/api/app.py` and `src/jamp/api/router.py`; related DTOs and tests were located. Tests were not executed on the comparison SHA as part of this audit. No live deployment behavior is asserted.

## 1. Feature status comparison

| Component | Baseline `4a1daeb` | Main `0aadb070` | Notes |
|---|---|---|---|
| `POST /v1/execute` | IMPLEMENTED | IMPLEMENTED | Main handler exists; tests are present. |
| Verification API | IMPLEMENTED | IMPLEMENTED | Includes `/v1/verify`, `/v1/verify-verdict`, and `/v1/verify-chain`. |
| Verdict list | NOT IMPLEMENTED | IMPLEMENTED | `GET /v1/verdicts`; organization-scoped list with pagination/filtering. |
| Dashboard stats API | NOT IMPLEMENTED | IMPLEMENTED | `GET /v1/stats`; organization-scoped persisted-row aggregates. |
| Evidence Graph API | NOT IMPLEMENTED | IMPLEMENTED | `GET /v1/verdicts/{verdict_id}/graph`; persisted verdict/evidence projection only. |
| `/health` | Not found in `src/jamp/api/app.py` | Present in separate `src/jamp/server/app.py` | Distinct ASGI app; do not conflate with API routes. |
| Chat | NOT IMPLEMENTED | NOT IMPLEMENTED | `src/jamp/api/router.py` defines `POST /chat`, but handler returns HTTP 501 and router is not mounted by `create_app()`. |
| Attachments | NOT IMPLEMENTED | NOT IMPLEMENTED | `src/jamp/api/router.py` defines `POST /attachments`, but handler returns HTTP 501 and router is not mounted by `create_app()`. |
| Router execute | NOT IMPLEMENTED | NOT IMPLEMENTED | `src/jamp/api/router.py` defines `POST /execute`, returns HTTP 501, and is distinct from `POST /v1/execute`. Router is not mounted by `create_app()`. |
| Pydantic DTOs | Not confirmed in baseline audit | Present for router contracts | `src/jamp/api/dto.py`; this does not establish typed request/response models for every `/v1/*` route. |
| History / Replay / Export | NOT IMPLEMENTED | UNKNOWN / HOLD | No complete HTTP workflow was established by this source inspection. |

**Status vocabulary:** IMPLEMENTED means implementation code was found. It does not mean independently VERIFIED. NOT IMPLEMENTED means the inspected route is absent or explicitly returns 501. UNKNOWN / HOLD means evidence is insufficient.

## 2. Main API surface observed

The current `src/jamp/api/app.py` registers these route groups:

- `POST /v1/verify`
- `GET /v1/verdict/{verdict_id}`
- `GET /v1/verdicts`
- `GET /v1/verdicts/{verdict_id}/graph`
- `GET /v1/stats`
- `POST /v1/classify`
- `POST /v1/execute`
- `POST /v1/verify-verdict`
- `POST /v1/verify-chain`
- `POST /v1/universal-verdict`
- `GET /v1/universal-verdict/{trace_id}`
- `GET /v1/jamp-verdict/{trace_id}`
- `GET /v1/provenance/{trace_id}`
- `POST /v1/telegram/webhook`

The three router definitions in `src/jamp/api/router.py` are separate and are not mounted into `create_app()` in the inspected revision:

- `POST /attachments` → HTTP 501
- `POST /chat` → HTTP 501
- `POST /execute` → HTTP 501

## 3. Status vocabulary — unresolved integration contract

Two status vocabularies are observed in separate layers:

**Persisted verdict / Dashboard API statuses**
- `CLEAN`
- `SUSPICIOUS`
- `HALLUCINATION_CAUGHT`
- `INCONCLUSIVE`
- `INTEGRITY_VIOLATED`

**Runtime claim aggregation statuses**
- `VERIFIED`
- `CONTRADICTED`
- `INCONCLUSIVE`
- `PARTIAL`

No status mapper is claimed to exist. A proposed mapping such as `CLEAN → VERIFIED` is not established by this audit and must not be implemented as an assumed one-to-one translation. Semantics, provenance, and aggregation rules require an explicit contract and tests before mapping.

## 4. Evidence limitations

- No test suite was run on `0aadb070a7ddc9d59806ad5cfe95eda336c5aa66` during this read-only audit.
- Located test files establish test presence only; they do not prove test success on this SHA.
- No terminal CI Run → Job → Artifact evidence is included in this document.
- No live server or production behavior was tested.
- Full OpenAPI request/response contracts for all `/v1/*` routes were not audited.
- Dashboard UI existence and route implementation do not prove full feature completeness.

## 5. Follow-up

Track the architectural work separately in GitHub Issue **[Tech Debt] Unify API routing and status enums**. That work must decide and test:
1. Whether `server.app` should mount or wrap the canonical API application, without creating duplicate application state.
2. The lifecycle and disposition of the unmounted HTTP 501 router endpoints: implement behind real capabilities or remove with explicit migration/deprecation.
3. A versioned, semantics-preserving status translation contract; do not assume `CLEAN → VERIFIED`.
4. Tenant isolation, authentication, OpenAPI schemas, and regression coverage for the unified ASGI surface.

**Change policy:** this document is a historical snapshot. Update it only with a new dated/SHA-scoped audit section; do not silently rewrite historical observations.
