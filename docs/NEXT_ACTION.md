# JAMP Next Action

## Current state

-   Mode: `READ-ONLY AUDIT / DOCUMENT REVIEW`
-   Baseline inspected: `3917c484e00cc0439695c16362b724d1ddbcc4a2`
-   Recursive docs inventory: complete for this baseline
    (`truncated=false`, 94 files).
-   The three proposed decision-document paths were absent from this
    baseline.
-   Frozen Core: exact locked blob match; Δ=0.
-   No repository files have been created or changed by this
    preparation.

## Task 1 --- Review these three proposed documents

Files prepared for review:

1.  `docs/DECISION_MAP.md`
2.  `docs/DECISION_LOG.md`
3.  `docs/NEXT_ACTION.md`

Definition of Done:

-   [ ] Decision IDs, statuses, and evidence boundaries approved.
-   [ ] Product PAUSE is kept separate from the tenant-isolation P0.
-   [ ] `OBSERVED: OWNERSHIP_NOT_MODELED` is distinguished from runtime
    disclosure and from a verified isolation result.
-   [ ] `VERIFIED: ISOLATION_ENFORCED`,
    `VERIFIED: CROSS_ORG_DISCLOSURE_REPRODUCED`, and
    `INCONCLUSIVE / HOLD` semantics approved.
-   [ ] P0 operational record provenance is the API key authenticated on
    the real create request; this does not imply a persisted owner/org
    field.
-   [ ] P0 test's real app, auth, AuditPersistence JSONL path, and
    actual storage topology requirements approved.
-   [ ] Missing-trace behavior is checked separately for each route;
    only `/v1/jamp-verdict/{trace_id}` is currently reported as 404.
-   [ ] No unsupported claim is promoted from OBSERVED/INFERRED/UNKNOWN
    to VERIFIED.

**No repository write, branch creation, commit, or PR is part of this
task.**

## Task 2 --- Only after explicit approval

After the user approves the contents and explicitly authorizes
repository publication:

1.  Refresh `main` SHA and open PR inventory.
2.  Re-check that the three target paths remain absent.
3.  Re-check Frozen Core blob SHA.
4.  Create a dedicated documentation branch from the refreshed `main`.
5.  Add only the three approved Markdown files. Do not change runtime,
    tests, workflows, thresholds, or existing docs.
6.  Review the exact diff and verify Frozen Core Δ=0.
7.  Report branch SHA and changed paths. Do not merge without separate
    explicit authorization.

## Task 3 --- P0 tenant-isolation investigation

This task is downstream of approval of the test specification; it is not
authorized by this document.

Read-only prerequisite:

-   Inspect `create_app()` wiring, the actual `AuditPersistence`
    configuration, JSONL file topology, and the real write path for each
    record type.
-   Determine the real create/read path and storage topology. The local
    review reports that `AuditPersistence` has no `organization` /
    `org_id` field or write parameter and uses one configured
    `audit_storage_path`; treat this as `OBSERVED` from that review,
    pending independent source verification.
-   For runtime controls, associate each test record operationally with
    the key authenticated on its real create request. Do not claim this
    is a persisted owner/org attribute.
-   If real authentication, create-key provenance, or the actual
    production write/read path cannot be established, record the affected
    record-type result as `INCONCLUSIVE / HOLD`. A direct persistence
    write is not enough unless the production call path demonstrably
    propagates the authenticated request context. Do not manufacture
    per-org stores or test-only filters.
-   If a real route creates a record under key A and key B retrieves
    it, classify as `VERIFIED: CROSS_ORG_DISCLOSURE_REPRODUCED` once
    the two real organization/key identities and exact request/response
    evidence are preserved.

Then, only with explicit authorization, implement and run the
integration test described in `docs/DECISION_LOG.md` under JAMP-DEC-001.

P0 Definition of Done:

The user approved **18 controls total** on 2026-11-01 19:01 UTC: six
positive, six cross-org negative, and six missing-trace controls.
`OWNERSHIP_NOT_MODELED` is a separate architecture observation, not an
additional runtime control. This approval is limited to test scope; it
does not approve repository publication or authorize test implementation.

-   Six positive controls (A→A and B→B for Verdict, Provenance,
    UniversalVerdict) succeed.
-   Six cross-org negative controls (A→B and B→A for all three routes)
    refuse without leaking foreign record data.
-   Six missing-trace controls (two keys × three routes) match each
    route's documented API contract.
-   The test uses real app/auth/persistence and the actual configured
    JSONL path.
-   Results are preserved as raw evidence.
-   Terminal CI evidence is recorded by SHA → workflow → run → job →
    conclusion → artifact.
-   Frozen Core Δ=0 is checked on the tested SHA.
-   Architecture observation is separately classified as
    `OBSERVED: OWNERSHIP_NOT_MODELED`, where source evidence supports it.
-   Runtime result is classified as `VERIFIED: ISOLATION_ENFORCED`,
    `VERIFIED: CROSS_ORG_DISCLOSURE_REPRODUCED`, or
    `INCONCLUSIVE / HOLD`.

No automatic remediation, Ed25519 implementation, product development
restart, or merge follows merely from completion of this test. Each
requires its own evidence-backed decision and, where applicable,
explicit authorization.

## Publication authorization update --- 2026-11-01 19:02 UTC

The user explicitly authorized publication of the three decision documents.
The publication scope is limited to the three Markdown paths listed above.
The authorized delivery is a dedicated documentation branch and pull
request; merge is not authorized. No code, tests, workflows, thresholds,
policies, or Frozen Core changes are in scope. The historical checklist
above records the state before this authorization and is not a current
write prohibition.
