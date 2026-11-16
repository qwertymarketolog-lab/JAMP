# ADR-001: Separate React frontend

- Status: Accepted
- Date: 2026-11-16
- Decision owners: JAMP maintainers

## Context

JAMP currently serves an authenticated server-rendered dashboard through FastAPI and Jinja2. The next product interface needs a richer application shell: persistent navigation, reusable evidence views, and future marketplace and Telegram surfaces. Expanding the Jinja2 page into a client-heavy application would couple presentation to server templates and make independent frontend evolution difficult.

## Decision

Create an independently buildable single-page frontend under `frontend/` using React, TypeScript, Vite, and Tailwind CSS. Keep the existing Jinja2 dashboard and its routes unchanged. Vite proxies the `/api` prefix to the local FastAPI origin and strips that prefix, so a future browser request to `/api/v1/verify_text` reaches the existing backend route `/v1/verify_text`.

This first increment is a static layout only. It does not call APIs, authenticate users, verify claims, or imply that marketplace or Telegram workflows are implemented.

## Consequences

- Python remains the backend/runtime authority; Node.js is a frontend build-time toolchain.
- Frontend dependencies and build output are isolated under `frontend/`; generated `node_modules/` and `dist/` are not committed.
- CI must build the frontend on pull requests.
- TypeScript API types document the observed `/v1/verify_text` response contract; they are not a runtime validator and do not activate integration.
- The existing backend authenticates `/v1/verify_text` through `require_api_key`. The current signed HttpOnly dashboard cookie is read-only: `require_api_key` accepts it only for GET/HEAD and rejects POST with 403. Therefore the future POST integration cannot rely on the existing cookie session unchanged; a separate security-reviewed backend change must define write-session authorization and CSRF/origin protections. No credentials are embedded in frontend code.
- Future marketplace, model/provider, Evidence, and Telegram screens must be backed by real backend contracts and must distinguish verified data from unavailable or planned functionality.

## Alternatives considered

1. Extend Jinja2 with more client-side JavaScript: rejected because it would entangle the new application shell with the legacy server-rendered admin surface.
2. Next.js: rejected for this stage because server-side rendering and a Node application server are not currently required; Vite provides a smaller static build.
3. React without TypeScript: rejected because API/evidence payloads need explicit, reviewable contracts.

## Frozen Core

This frontend decision does not require changes to `src/jamp/run.py`. Its locked blob remains `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`; expected delta is zero.
