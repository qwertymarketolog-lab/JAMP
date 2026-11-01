# JAMP Next Action

## Current state

- PR: #496 — OPEN / Draft / not merged.
- Branch: `docs/decision-evidence-map-20261101`.
- Current PR head after documentation corrections: `e899576326715b86be59be4f9c20018626a72bf5`.
- Previous evidence snapshot audited for the 14-run discrepancy: `c159b224a8b577cfc3ec308b1590497865308ebb`.
- Base: `3917c484e00cc0439695c16362b724d1ddbcc4a2`.
- Frozen Core: `src/jamp/run.py` blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`; exact match on inspected head, Δ=0.
- PR scope remains exactly three documentation files. No runtime, tests, workflows, thresholds, policies, dependencies, or Frozen Core changes are authorized.
- PR remains Draft; merge is not authorized.

## Single next action — P0 read-only route and storage contract inspection

Inspect the current source at an exact recorded SHA and establish the real application path before implementing any tenant-isolation test.

Scope:

1. Trace `create_app()`, API-key authentication, and the three GET handlers:
   - `/v1/jamp-verdict/{trace_id}`
   - `/v1/provenance/{trace_id}`
   - `/v1/universal-verdict/{trace_id}`
2. Trace the actual `AuditPersistence` JSONL read/write path and configured storage topology.
3. For each record type, identify whether a real authenticated create route exists. If not, trace the exact production write call path and determine whether authenticated request context reaches it.
4. Establish missing-trace behavior independently for each route from handler/source. Current recorded knowledge: JAMP verdict is reported as 404 when the read returns `None`; Provenance and UniversalVerdict remain UNKNOWN until inspected.
5. Preserve the distinction between operational create-key provenance and a persisted owner/org attribute. Do not manufacture per-organization stores or test-only filters.

Definition of Done:

- Exact inspected commit SHA is recorded.
- Each of the three route handlers and its persistence read method is identified.
- Actual JSONL path/topology and write methods are identified from source.
- Each record type is classified as having a real authenticated create route, a proven production call path carrying authenticated context, or `INCONCLUSIVE / HOLD`.
- Missing-trace contract is recorded separately for all three routes; unknown behavior remains UNKNOWN.
- `OBSERVED: OWNERSHIP_NOT_MODELED` remains an architecture observation, not a runtime disclosure verdict.
- No runtime test is implemented or run during this read-only action.
- Frozen Core blob is checked against the locked SHA; expected Δ=0.

Exit condition: publish the source-backed inspection findings and only then request authorization for the 18-control integration test (6 positive, 6 cross-key negative, 6 missing-trace). No remediation, merge, product restart, or additional implementation follows automatically.

## Evidence boundary

- DEC-007 baseline CI qualification: UNKNOWN.
- DEC-008 required-check evidence: HISTORICAL; verified only for old PR head `1ff1726e...`.
- DEC-009 current-head complete workflow inventory: HOLD; 14 run-level records were observed on `c159b224...`, but jobs/artifacts were not independently inspected in this update.
- PR CI does not establish post-merge CI.
