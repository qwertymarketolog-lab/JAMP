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
| Evidence System | VERIFIED | Canonical records and content commitments || Provenance Tracking | VERIFIED / HOLD | Temporal consistency verified; execution binding unresolved |
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


## Target Product Vision and Composition

**Status:** strategic target / roadmap hypothesis. This section records the product direction discussed on 2026-10-15. It does not claim that the complete platform, interfaces, integrations, or commercial capabilities are implemented.

### Product thesis

JAMP is intended to become an **evidence-first infrastructure platform for checking the results of AI models, AI agents, software systems, and controlled automated processes**. It is not intended to be another general-purpose chatbot or a foundation-model provider.

The central product question is:

> What was actually executed, what evidence supports the result, what remains unknown or contradictory, and is there enough evidence to justify the next action?

AI models and agents are instruments that produce observations or perform bounded tasks; they are not authorities. JAMP must preserve the distinction between raw evidence and derived interpretation and must not manufacture a positive status from missing or inconclusive evidence.

### Target logical composition

The intended platform is organized into separable layers:

1. **JAMP Core / Evidence Infrastructure** — evidence records, provenance, conflict preservation, integrity checks, explicit epistemic states, deterministic qualification and audit history. The Frozen Core remains protected.
2. **Execution and agent adapters** — controlled connections to models, coding agents, research tools, CI jobs and external APIs. Adapters return observations and artifacts; they do not decide that their own outputs are verified.
3. **Capability Router and policies** — selects a compatible executor using known capabilities, task profiles, latency/cost constraints and policy. Unknown, unsupported or insufficiently evidenced routes fail closed.
4. **Evidence Registry and lineage** — links task, model/provider and version where available, parameters, source inputs, Run → Job → artifact, checks, derived summaries and final decision. Raw evidence remains distinguishable from summaries.
5. **JAMP API and integrations** — the programmatic boundary for applications and external systems. Extend the existing FastAPI serving lineage; do not create a parallel backend.
6. **User interfaces** — Telegram as a lightweight control/notification surface; responsive web/PWA as the likely first general UI; mobile and desktop packaging only after the shared API and user journey are stable.
7. **Extension ecosystem** — separately governed adapters and domain modules that add integrations or checks without bypassing core contracts or changing the Frozen Core.

Conceptual flow:

```
User / Application / Telegram / Web-PWA / API
                      |
              JAMP API / Adapter
                      |
          Router + execution policies
                      |
       Model / Agent / Tool / CI / Data source
                      |
             Run -> Job -> Artifact
                      |
       Provenance + integrity + rule checks
                      |
         VERIFIED / CONTRADICTED /
          INCONCLUSIVE / UNKNOWN
                      |
       Evidence-backed report and audit trail
```

This is a target architecture, not a claim that every edge is currently wired end-to-end. Each capability requires its own contract, implementation evidence and acceptance decision.

### Product delivery sequence
The delivery roadmap already recorded above (Stages A–G) remains the operational source for the serving/API/UI path. The strategic target is reached incrementally:

1. **Reliable evidence and execution path:** confirm one canonical API entry point, connect only explicitly contracted execution paths, preserve Run → Job → artifact lineage, and verify real terminal outcomes.
2. **Usable first product:** complete the end-to-end user journey through the existing API; prefer a responsive web/PWA before separate native applications. Telegram can remain a practical initial interface.
3. **Operational readiness:** authentication/authorization, secret handling, bounded execution, monitoring, retention policy, deployment/recovery documentation and security tests must be defined before claiming production readiness.
4. **Developer platform:** stabilize API contracts and documented adapters so external developers can connect models, tools and their own applications.
5. **Extension ecosystem:** introduce versioned plugin contracts, compatibility checks, permissions, isolation, provenance requirements and an explicit review/revocation process.
6. **Enterprise and domain applications:** pursue only after a narrow use case demonstrates value with real users. Possible research areas include software engineering/CI, AI-agent evaluation, source-backed research and enterprise document workflows. These are market hypotheses, not validated demand or shipped capabilities.

### Plugin policy and rollout

Plugins are an implementation and integration mechanism, not the product goal. Do not install a large bundle of extensions merely because it is available in a catalog.

Before adopting a candidate, inspect its exact upstream repository, license, maintenance/activity, supported clients, permissions, network/data handling, secret access, command execution behavior, update mechanism and measurable benefit. Confirm that the capability is not already supplied by an existing JAMP integration.

Evaluate at most one candidate per concrete need in an isolated, read-only or otherwise bounded experiment. Measure time, cost, failure rate and review quality against the existing workflow. Reject a plugin if it requires unnecessary privileges or cannot be safely isolated.

Initial categories to evaluate, in order of practical need:
- GitHub/CI navigation and evidence retrieval, reusing existing connected capabilities where sufficient;
- independent code review and test assistance;
- secret/dependency/security scanning;
- bounded agent orchestration;
- context and progress management only if a measured baseline shows material waste.

Runtime JAMP plugins must never be allowed to silently upgrade evidence status, bypass fail-closed policy, write to the Frozen Core, access unrestricted secrets, or perform privileged actions without the relevant authorization. Agent claims are not verification evidence by themselves.

### Product boundaries and non-goals

- JAMP is an evidence and verification layer around existing models and tools; it does not need to train or own a foundation model.
- A green CI run, HTTP 2xx response, successful agent completion, model consensus or matching SHA-256 alone does not prove a broader product claim. Evidence must be relevant to the exact claim.
- The Frozen Core invariant remains `src/jamp/run.py`, blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`, with required `Δ = 0`.
- New UI, integrations, plugins and domain products should be developed outside the Frozen Core through explicit contracts and isolated tests.
- JAMP FURNITURE is a separate applied-business direction. It may reuse general evidence-first engineering patterns, but its business processes and product model must not be merged into JAMP without an explicit architectural decision.
- Commercial packaging, subscription/API pricing, enterprise deployment and industry-specific compliance are future hypotheses requiring customer discovery, security work and validation; none is implied by this roadmap.

### Acceptance gates for advancing the target

Do not describe JAMP as a production-ready universal platform until evidence supports all applicable gates:

- a canonical and documented API contract;
- a verified end-to-end task → execution → Run/Job/artifact → provenance/result path;
- explicit failure, UNKNOWN, INCONCLUSIVE, HOLD and REFUSE behavior;
- reproducible CI evidence bound to the exact commit and artifacts;
- confirmed Frozen Core invariant (`Δ = 0`);
- defined identity, authorization, secrets, isolation and retention boundaries;
- demonstrated user value in at least one narrow use case;
- an operational deployment and recovery process.

Until these gates are met, the broader platform remains a target architecture and roadmap, not a verified product capability.

## AI Development Team and Governance

**Recorded:** 2026-10-15  
**Status:** agreed operating model / governance contract proposal. This section records roles and boundaries; it does not claim that Codex or any other agent is already connected, continuously running, or authorized to perform actions.

### Roles and accountability

- **Human owner / Architect (user):** owns product direction, priorities, acceptance criteria, risk tolerance, and final architectural decisions. Approves merges and any exception to protected boundaries.
- **Codex / Implementer:** primary coding worker when connected and available. Inspects repository state before acting, selects an assigned task, works on an isolated branch/worktree, makes the smallest justified change, runs relevant checks, and prepares a PR with evidence. It has no authority to merge its own changes or directly modify `main`.
- **ChatGPT / Coordinator and independent auditor:** helps break goals into verifiable tasks, inspects repository and CI evidence, reviews diffs and acceptance criteria, identifies gaps and risks, and reports PASS / FAIL / HOLD only when supported. It must not treat its own analysis or an agent's assertion as verification evidence.
- **Other AI systems / Specialists and adversarial reviewers:** perform bounded, explicitly assigned research or review (for example, security, API contracts, tests, dependency risk, performance, or counterexample search). They return source-linked findings and uncertainty, not unqualified approval.
- **GitHub / CI / evidence artifacts:** provide the durable source of truth for changes, reviews, test executions, Run → Job → artifact lineage, and recorded decisions. A model's narrative is not a substitute for these records.

### Authority boundaries

1. The human architect retains final product and merge authority.
2. Agents work through isolated branches and pull requests. No direct writes to `main`; no automatic merge.
3. No agent may self-approve its own implementation. Implementation and review should be separated where feasible; where an independent reviewer is unavailable, status remains REVIEW / HOLD rather than claiming independent approval.
4. Before creating a branch, file, issue, or PR, inspect existing repository state, open PRs, branches, and relevant evidence. Extend an existing canonical artifact when appropriate; do not create duplicate work.
5. Do not change thresholds, suppress failing checks, rewrite raw evidence, or turn missing/unknown/inconclusive results into PASS / VERIFIED.
6. Do not expose secrets, credentials, private user data, or unrestricted tokens in prompts, logs, artifacts, or PRs. Grant only the minimum required permissions.
7. Frozen Core is protected: `src/jamp/run.py`, expected blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`, required invariant `Δ = 0`. Any proposed exception requires explicit human authorization and its own evidence-backed change process; routine agent tasks must leave it unchanged.
8. An agent may attempt bounded self-correction, but every attempt must be recorded and re-tested. Repeated failure or missing evidence results in HOLD, not an invented success.

### Task lifecycle

Use the existing GitHub Issues, branches, PRs, and Actions as the initial task-control surface. Do not build a second dispatcher until a read-only capability audit proves it is needed.

- `READY` — scope, owner, acceptance criteria, protected paths, and required evidence are explicit.
- `IN_PROGRESS` — one named implementer owns the active change; overlapping edits are coordinated.
- `REVIEW` — implementation is complete enough to inspect; no merge is implied.
- `HOLD` — required context, permissions, independent review, Run/Job/artifact evidence, or acceptance criteria are missing or contradictory.
- `DONE` — acceptance criteria are met, relevant evidence is linked, and the human owner accepts the result.
- `REJECTED` — the proposal fails its acceptance criteria or violates a protected boundary.

Every task handoff should include: task ID/link; base commit and branch; exact scope; files allowed/protected; acceptance criteria; commands/checks actually run; terminal Run → Job → artifact links where applicable; changed-file review; Frozen Core comparison; unresolved risks; and the next decision requested.

### Evidence and review protocol

1. Inspect before editing: current base SHA, relevant source, existing issues/PRs/branches, and prior results.
2. State the hypothesis and expected observable result before a risky change.
3. Keep raw evidence separate from summaries and bind conclusions to exact commits, runs, jobs, and artifacts.
4. Verify terminal CI status and the relevant Job and artifact contents. A green workflow alone does not prove an unrelated or broader claim.
5. Preserve explicit `UNKNOWN`, `INCONCLUSIVE`, `CONTRADICTED`, `REFUSE`, and `HOLD` states. Missing evidence must not be replaced by inferred or synthetic evidence.
6. Prefer a distinct reviewer for adversarial review. Ask reviewers to find counterexamples and defects, not to agree with the implementer.
7. The final report states what changed, what was actually tested, what evidence exists, what remains unverified, and whether the next step is PASS, FAIL, or HOLD.

### Initial rollout

- First connect and verify the actual Codex ↔ GitHub capability and permissions; this document alone does not establish a working connection or paid/cloud availability.
- Start with a read-only repository and open-PR inventory; do not let the first task rewrite code.
- Reuse existing autonomous-worker trust-boundary and safety-contract work (including PRs #170 and #176) and inspect the existing daily evidence agent work (PR #365) before proposing new orchestration.
- Run one bounded pilot task through branch → tests → CI Run → Job → artifact → independent review. Inspect the results before granting broader permissions or unattended task chaining.
- Only after the pilot is accepted should we consider scheduled task selection or multi-agent orchestration. Any schedule, write permission, or expanded autonomy is a separate decision with explicit limits and rollback.

This governance section is a working agreement, not evidence that these controls are already enforced by code or GitHub settings. Enforcement must be verified separately.

## Future API Integration and Evidence Plugins

**Recorded:** 2026-10-15  
**Status:** future product direction / unvalidated roadmap hypothesis. This section records intended exploration only; it does not claim that the connectors, collection pipeline, analysis plugins, or user interface are implemented or verified.

### Goal

Allow JAMP to connect to external services through documented APIs, ingest source data with explicit provenance, run bounded analysis, and return findings linked to the underlying evidence. The value proposition is not merely connecting many APIs: it is making each derived conclusion inspectable, reproducible where possible, and honest about missing, partial, or contradictory evidence.

### Candidate source families

Evaluate sources individually based on API availability, authorization, terms, data sensitivity, maintenance burden, and a concrete user need:

1. **YouTube comments — first proposed feasibility pilot.** Retrieve accessible public comment threads and replies through the official YouTube Data API where permitted. Record pagination, quotas, comments-disabled cases, inaccessible data, and collection limits. Do not assume all comments or all replies were retrieved.
2. **GitHub and CI — reuse existing integration capability first.** Read repositories, issues, pull requests, workflow runs, jobs, and artifacts where authorized. Avoid building a second GitHub connector if existing connected tools cover the required operation.
3. **Reddit and public discussion sources.** Consider only documented, permitted API access and retain source links and collection constraints.
4. **Customer feedback and app reviews.** Consider Google Play Developer APIs, App Store Connect, CRM/support systems, and other feedback sources where the account has authorized access.
5. **Marketplaces and commerce sources.** Consider official seller/catalog APIs and authorized exports for product details, reviews, orders, or prices. Do not assume public access to private seller data, sales metrics, or complete review corpora.
6. **Other business systems.** Add a connector only when a specific workflow and authorized source justify it.

This list is a candidate inventory, not a statement that every source offers a public API or that access has been tested.

### Proposed logical flow

```
Source URL / Authorized Account
          -> Source Adapter
          -> Raw Capture + Retrieval Metadata
          -> Schema / Integrity / Completeness Checks
          -> Evidence Records + Provenance
          -> Bounded Analysis Plugin
          -> Claim-to-Source Links + Limitations
          -> Reviewable Report / API Response
```

Adapters acquire and describe source data; they must not certify the correctness of derived conclusions. Analysis plugins produce derived interpretations that remain distinguishable from raw records.

### Minimum evidence contract for each connector

- Source/platform and documented API operation or authorized export path.
- Request scope, retrieval timestamp, pagination/cursor state, and applicable account/permission context without exposing secrets.
- Source identifiers and stable source links where available.
- Raw response or a policy-compliant retained representation, with a content digest when feasible.
- Counts requested, fetched, skipped, and failed where measurable; explicit reasons and limits.
- API version, adapter version, relevant parameters, rate-limit/quota behavior, and errors.
- Separation of raw observations from normalized records, model-generated labels, summaries, and final claims.
- Traceable mapping from each material report claim to supporting and contradicting source records.
- Explicit UNKNOWN / INCONCLUSIVE / HOLD / REFUSE when access, coverage, schema, or evidence quality is insufficient. No synthetic success and no claim that a partial sample represents an entire audience or market.

### First pilot: YouTube comment evidence

The first experiment should be narrow and read-only:

1. Use one user-supplied video URL.
2. Check official API access, credential requirements, quota implications, and whether comments are available before implementing a reusable connector.
3. Collect only the records allowed by the API and applicable rules; preserve identifiers and retrieval metadata.
4. Produce a small report grouping themes, questions, complaints, ideas, and counterexamples, with links to the exact comments that support each finding.
5. Manually inspect a sample of source records against the report and record sampling/coverage limitations.
6. Decide whether to proceed to a versioned connector contract based on observed usefulness, access reliability, cost, and evidence quality.

A successful pilot means the source-to-report chain and its limitations are inspectable; it does not prove market demand, audience-wide consensus, or the truth of every model-generated interpretation.

### Delivery order and gates

- **P0 — Source feasibility:** read-only access check; no code, credentials in repository, or Frozen Core changes.
- **P1 — Connector contract:** define input/output schema, authorization boundary, pagination, error states, provenance fields, retention, and tests using captured or synthetic fixtures clearly labelled as such.
- **P2 — One vertical implementation:** implement and test the YouTube path only if P0 demonstrates feasible permitted access.
- **P3 — Evidence-linked analysis:** verify that report claims can be traced to raw records and that counterevidence and uncertainty remain visible.
- **P4 — Reusable adapter interface:** generalize only after the first connector demonstrates value; add other sources one at a time.
- **P5 — Product integration:** connect to the existing JAMP API and UI only after the canonical API path and execution/provenance contracts are verified. Do not create a parallel backend or a second task dispatcher.

### Security, privacy, and architectural boundaries

- Use official APIs or explicitly authorized exports; do not bypass access controls, authentication, rate limits, platform restrictions, or privacy settings.
- Keep credentials in an appropriate secret store or environment configuration; never commit tokens or place them in logs/artifacts.
- Define data minimization, retention/deletion, access controls, and handling of personal data before storing or sharing collected content.
- Treat external text and comments as untrusted input, including possible prompt-injection attempts; source content must not be allowed to instruct privileged agents or trigger actions.
- Enforce bounded network access, timeouts, size limits, retries, and quota handling.
- Preserve the Frozen Core invariant: `src/jamp/run.py`, expected blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`, required `Δ = 0`. New connectors and analysis plugins must remain outside the Frozen Core and must not upgrade their own evidence status.
- Before adding files or PRs, inspect current implementation and open work; extend existing contracts and integration points rather than creating duplicate connectors or roadmaps.

### Acceptance gate

Do not mark a connector or its findings VERIFIED merely because an API call returned HTTP 2xx or an AI produced a confident summary. Require source-bound records, documented coverage and limitations, relevant automated tests, inspection of representative claims against raw evidence, and terminal CI Run → Job → artifact evidence for implementation changes. Until then, this remains a future roadmap item.

