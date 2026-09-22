# Post-Merge Zero-Job Workflow Forensic Record

Date: 2026-09-22

## Scope

Commit under investigation: `cb9dc767b0294d30c042a40c72a6503dab31a85e`.

This record documents the post-merge GitHub Actions anomaly observed on `main`. It does not modify workflow definitions and does not treat workflow-level failure as a test failure.

## Verified current evidence

Two workflow runs were created at `2026-09-22T19:47:58Z` for the same push:

| Workflow | Run ID | Workflow ID | Check Suite | Conclusion | Jobs |
|---|---:|---:|---:|---|---:|
| `.github/workflows/import-historical.yml` | `35776095200` | `353142147` | `96870578435` | failure | 0 |
| `.github/workflows/test.yml` | `35776096278` | `353118495` | `96870581740` | failure | 0 |

Both runs have:

- event: `push`
- branch: `main`
- head SHA: `cb9dc767b0294d30c042a40c72a6503dab31a85e`
- status: `completed`
- `jobs=[]`

Six other workflows for the same push subsequently materialized jobs and completed successfully.

## Trigger evidence

`import-historical.yml` is configured for:

`push.branches = import/jamp-from-visual-merchant-hub`

The investigated push is to `main`. Therefore its `assemble` job is not applicable to this push.

`test.yml` is configured for `push.branches = main`. Its job condition includes:

`github.ref == 'refs/heads/main'`

For the investigated push this condition is expected to evaluate true, yet the workflow produced zero jobs.

## Historical forensic pattern

Earlier push events showed the same two zero-job workflow-level failures immediately before normal materialized workflow suites. The repeated pattern is observed at approximately:

- 17:09:05 / 17:09:06
- 19:32:33 / 19:32:34
- 19:37:24 / 19:37:25

The available Check Suite objects do not expose the historical workflow ID/name needed to prove the individual historical first/second mapping. Therefore that historical mapping remains UNKNOWN.

The current mapping is VERIFIED from the workflow run metadata above.

## State

**Post-merge main: INCONCLUSIVE / HOLD**

**ROOT CAUSE = UNRESOLVED**

The evidence supports a workflow-dispatch/materialization anomaly. It does not establish a pytest, Ruff, Mypy, runtime, production-code, or repository-test failure.

## Non-actions

No workflow definition was changed.

No test, threshold, provenance identity, or Frozen Core was changed.

No rerun was used to manufacture GREEN evidence.

Frozen Core remains LOCKED:
`src/jamp/run.py` blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

## Evidence classification

- **OBSERVED:** two workflow-level failures with zero jobs; repeated historical zero-job prefix.
- **VERIFIED:** current workflow/run/check-suite identities and current trigger configuration.
- **INFERRED:** failure occurs before ordinary job execution/materialization.
- **UNKNOWN:** GitHub Actions internal mechanism producing `conclusion=failure` with zero jobs; exact historical suite-to-workflow mapping.
