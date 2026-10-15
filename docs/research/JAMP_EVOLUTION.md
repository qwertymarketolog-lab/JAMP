# JAMP Evolution

## Purpose

JAMP remains independent of any specific AI model, hardware platform, or input data format.

The proven JAMP core is the foundation. Further development proceeds through isolated research levels and experiments rather than by weakening or replacing established contracts.

The purpose of this document is to provide an architectural map for future research. It does not itself establish experimental results or close research hypotheses.

## Foundation

The current JAMP foundation is built around:

- **Ω — search space**
- **A — actions**
- **C — constraints**
- **O — observations**
- evidence-first experimentation
- explicit provenance
- conflict handling
- replay and auditability
- falsifiability
- explicit execution states
- controlled research branches
- separation of proven results from hypotheses and session-only observations

The guiding loop is:

**observation → question → controlled experiment → result → verification → next question**

JAMP is intended to preserve the evidence chain through this loop.

## Architecture stack

The current research architecture is organized as a progression from protected foundations to execution and replay infrastructure:

**Frozen Core → Evidence → Provenance → Conflict → Atomic Observation → Multi-AI Federation → Evidence Acquisition → Deterministic Qualification → Immutable Evidence Bundle → Offline Replay → Experiment Engine → Adaptive Research Loop → Research OS / Domain Products**

These are architectural levels, not separate JAMP versions. A level may remain in progress or HOLD while later contracts are being designed.

### Foundation

1. **Evidence** — observations, evidence records, deterministic artifacts, and explicit epistemic status.
2. **Provenance** — execution identity, source lineage, temporal consistency, and explicit binding to frozen specifications and criteria.
3. **Conflict** — contradictory evidence is preserved rather than silently resolved.
4. **Atomic Observation** — observations are decomposed into deterministic, traceable atomic records with preserved source provenance.

### Multi-AI Federation

Different AI models are treated as interchangeable research instruments rather than privileged sources of truth.

The current AnyModel v3 audit contains **87 models × 30 checks = 2,610 checks**. Capability qualification remains separate from provenance authentication.

### Evidence Acquisition & Replay

The current implementation direction is:

**Multi-AI audit → Execution Evidence Acquisition → Deterministic Checker & Qualification → Immutable Evidence Bundle → Offline Replay**

PR #225 defined the R18–R24 frozen-input contract. PR #226 added the Evidence Acquisition Contract v0 to main. The contract is design-only/pre-freeze; implementation must establish its own contract tests and terminal CI evidence before claiming conformance.

### Experiment Engine

Use JAMP to coordinate controlled experiments across models, data, transformations, parameters, and environments.

### Adaptive Research Loop

Allow subsequent research actions to depend only on verified observations and experimental results while preserving the evidence chain and preventing unsupported state changes.

### Research OS / Domain Products

The long-term target combines the verified evidence infrastructure into reproducible research workflows and domain-specific products without coupling those products to the Frozen Core.

## AI and hardware are tools

AI models are research instruments.

Data and files are research material.

Hardware is a compute environment.

JAMP is the research, evidence, provenance, conflict, and audit contour connecting them.

A new model, chip, quantization format, or input modality must not require changes to the proven core merely because it is new.

Any core change requires its own evidence and controlled experiment.

## Architectural rule

**Do not modify a proven contract to accommodate an untested capability.**

New capabilities should first enter through isolated research artifacts and tests.

Only evidence demonstrating that an architectural change is necessary and justified can support a subsequent core change.

## Current Experimental & Architecture State

### Verified foundations

- **Frozen Core invariant:** src/jamp/run.py remains at blob 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a; Δ = 0.
- **Evidence:** canonical evidence commitments and deterministic artifacts are established.
- **Provenance:** historical AnyModel v3 evidence is temporally consistent, while execution binding remains **HOLD / unresolved**.
- **Atomic Observation:** deterministic observation identity is established without changing the Frozen Core.
- **Multi-AI audit:** AnyModel v3 contains 87 models × 30 checks = 2,610 observations/checks.

### Current focus: Evidence Acquisition & Deterministic Qualification

- The former “next step: Atomic Observation Decomposition” marker is obsolete; Atomic Observation is now an established foundation layer.
- **R18–R24 Frozen-Input Contract:** defined in PR #225.
- **Evidence Acquisition Contract v0:** merged in PR #226; design-only/pre-freeze.
- **AnyModel qualification:** **INCONCLUSIVE / HOLD**; 25 candidates remain blocked by mandatory P0 evidence.
- **Next tactical target:** implement the deterministic checker runtime, immutable evidence bundle generation, and offline replay without modifying the Frozen Core.

### Current State Matrix

| Component | Status | Evidence boundary |
|---|---|---|
| Frozen Core | VERIFIED / FROZEN | src/jamp/run.py blob 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a; Δ = 0 |
| Evidence System | VERIFIED | Canonical records and content commitments |
| Provenance Tracking | VERIFIED / HOLD | Temporal consistency verified; execution binding unresolved |
| Conflict Handling | VERIFIED | Contradictions remain explicit |
| Atomic Observation | VERIFIED | Deterministic observation identity |
| Multi-AI Federation / AnyModel v3 | VERIFIED / ONGOING | 87 × 30 = 2,610 checks |
| AnyModel Qualification | INCONCLUSIVE / HOLD | 25 candidates blocked on mandatory P0 evidence |
| R18–R24 Frozen-Input Contract | DEFINED | PR #225 |
| Evidence Acquisition Contract v0 | MERGED | PR #226; design-only/pre-freeze |
| Execution Implementation | NOT YET IMPLEMENTED | Next working stage |
| Replay Engine | NOT YET IMPLEMENTED | Depends on executable evidence bundle/checker |
| Adaptive Research Loop | ACTIVE DEVELOPMENT | Infrastructure/control layer |
| Research OS / Domain Products | ROADMAP | Future target |


## Research discipline

For each new level, the preferred sequence is:

**SPEC → RED tests → reference operator → GREEN → CI → evidence → DECISION**

Research status must remain grounded in actual artifacts, commits, test output, and CI evidence.

This document is an architectural roadmap. It does not substitute for those results.

## Non-negotiable boundary

The proven JAMP core remains frozen unless a separate, evidence-backed research process demonstrates that a change is required.

The evolution of JAMP therefore proceeds outward from the foundation rather than by repeatedly rewriting the foundation.


## Product Delivery Roadmap: API → Web/PWA → Mobile & Desktop

**Recorded:** 2026-10-15  
**Purpose:** turn the existing evidence infrastructure into a usable application without replacing the existing backend or weakening evidence contracts. This section is an execution plan, not a claim that deployment or end-to-end delivery is complete.

### Current serving baseline (static source audit)

- The primary FastAPI application is `src/jamp/api/app.py`; it exposes `POST /v1/classify`, `POST /v1/execute`, and `GET /v1/provenance/{trace_id}`.
- The existing provider adapter is `src/jamp/provider/anymodel.py`. Missing provider configuration is intended to fail closed.
- Existing endpoint and audit persistence tests are present in `tests/test_api_endpoints.py` and `tests/test_audit_persistence.py`. Their existence is not evidence that they passed in this audit; no tests were run as part of the source review.
- `src/jamp/api/router.py` contains P32 Gateway routes whose chat/attachments/execute handlers return HTTP 501 because orchestration is not connected. The primary `create_app()` does not include that router.
- `src/jamp_app/api/app.py` is a separate minimal WSGI health/404 application; it must not be mistaken for the primary product API.
- Existing implementation lineage includes merged PRs [#295](https://github.com/qwertymarketolog-lab/JAMP/pull/295) (MVP API skeleton), [#317](https://github.com/qwertymarketolog-lab/JAMP/pull/317) (API/CLI serving layer v1), and [#344](https://github.com/qwertymarketolog-lab/JAMP/pull/344) (P32 API Gateway v0). Extend this lineage; do not create a second backend from scratch.
- The Frozen Core remains `src/jamp/run.py`, expected blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`, with required `Δ = 0`.

### Ordered execution plan

| Order | Stage | Required work | Exit evidence | Current status |
|---|---|---|---|---|
| A | Serving inventory | Read-only review of package/dependency declarations, documented launch command, configuration/environment variables, CI workflow coverage, and current API schemas. Check current PRs/branches before changing files. | Inventory report with exact paths, gaps, and source/CI references. | PARTIAL — route/source inventory done; launch/dependency/CI audit still required. |
| B | One canonical API contract | Decide which application is the product entry point; reconcile primary FastAPI routes with P32 Gateway contracts. Replace 501 only when the actual orchestration contract and tests exist. Avoid duplicate API implementations. | Contract table for endpoint, request/response schema, errors, provenance and fail-closed cases; tests cover every wired route. | BLOCKED — P32 orchestration is not connected and its router is not wired into the primary app. |
| C | End-to-end API verification | Exercise classify → execute/refuse → trace/provenance using controlled fixtures and a configured/unconfigured provider. Verify persistence and error paths. | Terminal CI Run → Job → artifact, with commit SHA, test results, and Frozen Core check. | NOT VERIFIED — source tests exist; this audit did not run them or inspect a new terminal CI artifact. |
| D | Responsive web app / PWA | Build a small responsive interface on the canonical API: submit task, show result and explicit execution/refusal status, show trace/provenance, and render actionable errors. Reuse existing UI files if present; check before adding new ones. | Browser/mobile viewport tests; API integration tests; clear UNKNOWN/INCONCLUSIVE/HOLD/REFUSE display; no false VERIFIED badge. | NOT STARTED / pending UI inventory. |
| E | Safe deployment baseline | Define deployment target and operator model; document environment configuration and secret handling; set production CORS/host policy, request limits, timeouts, health/readiness behavior, logs and data-retention boundaries. Add authentication/authorization only with a defined user/ownership contract. | Reproducible deployment instructions, configuration checks, and security-focused tests; no secrets committed. | NOT VERIFIED — no public production deployment confirmed. |
| F | Mobile and desktop delivery | First make the responsive PWA installable on Android and desktop browsers. Consider native wrappers only after the same API/UI flow is stable and measured requirements justify them. | Install/launch smoke tests on target devices, reconnect/error behavior, and a release artifact linked to its source commit. | ROADMAP. |
| G | Release gate | Verify the complete user journey and operational recovery; record limitations and known unsupported paths. | Terminal Run → Job → artifact, provenance trace, release commit, and explicit acceptance decision. | HOLD until A–F evidence is available. |

### Product status semantics

- HTTP 2xx or a visually successful screen is **not** sufficient evidence for `VERIFIED`.
- UI must display the backend's actual decision and evidence status; it must not upgrade UNKNOWN, INCONCLUSIVE, HOLD, or REFUSE to success.
- Provider unconfigured, unknown task/profile, missing evidence, and execution errors must remain explicit and fail closed.
- A successful CI run is not production-deployment evidence. Deployment, end-to-end behavior, and release status require their own evidence.
- Keep raw evidence separate from derived summaries and bind reported results to trace/run identifiers and artifacts where available.

### Next action

Complete **Stage A** as a read-only audit of dependency declarations, launch instructions, API request/response schemas, and relevant CI workflows. Then update this same roadmap with the verified findings before implementing UI or changing runtime contracts. Do not modify the Frozen Core or create a parallel backend.
