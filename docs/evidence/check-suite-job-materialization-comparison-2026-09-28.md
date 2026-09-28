# Check Suite / Job Materialization Comparison — 2026-09-28

## Scope

This addendum records the comparison requested for PR #221 head SHA `32f59c0c2e11389cd75aecb224bfda08ceaae8a6`. It does not alter workflow definitions, tests, thresholds, provenance identity, or Frozen Core.

## Verified evidence

| Check Suite | Workflow Run | Run conclusion | latest_check_runs_count | Jobs API |
|---|---:|---|---:|---|
| `98679956547` | `36443960510` import-historical.yml | failure | **1** | **1 job** |
| `98679960886` | `36443962082` test.yml | failure | **0** | **0 jobs** |

For Suite `98679956547`, the sole materialized Job is:

- Job ID: `109001539569`
- name: `G1 Trusted Lineage`
- status: `completed`
- conclusion: `success`
- created/started/completed: `2026-09-28T15:29:55Z`

For Suite `98679960886`:

- Jobs API: `total_count=0`
- `jobs=[]`

## Check Run identity qualification

The available GitHub connector does not permit direct retrieval of:

- `/check-suites/{suite_id}/check-runs`
- `/check-runs/{check_run_id}`

and no available GraphQL/checkRun read tool is exposed.

Therefore:

- Suite `98679956547` has exactly one Check Run according to `latest_check_runs_count=1`.
- Its only Job is `109001539569 / G1 Trusted Lineage`.
- **CheckRun ↔ Job identity = UNVERIFIED.**
- The Check Run ID/name itself remains UNKNOWN.

For Suite `98679960886`, `latest_check_runs_count=0`; no Check Run identity is available to inspect.

## Comparison

The two workflow runs are therefore not equivalent:

1. `import-historical.yml`: Run-level conclusion is `failure`, but one Job materialized and completed `success`.
2. `test.yml`: Run-level conclusion is `failure` and no Job materialized.

The first case is a Run-level / Job-level inconsistency. It must not be described as a simple `failure -> job -> success` sequence because the Run metadata reports creation/update/start at `15:29:23Z`, while the Job appears at `15:29:55Z`.
The second case remains a genuine zero-job result.

## Evidence classification

- **OBSERVED:** Suite `98679956547` reports one Check Run and its Run has one successful `G1 Trusted Lineage` Job; Suite `98679960886` reports zero Check Runs and its Run has zero Jobs.
- **VERIFIED:** exact Suite IDs, Run IDs, Job ID/name, Job conclusion, and Jobs API counts.
- **INFERRED:** the two failures have different materialization behavior.
- **UNKNOWN:** exact Check Run ID/name for Suite `98679956547`; GitHub internal mechanism producing these Run-level failures.

**ROOT CAUSE = UNRESOLVED**

**STATE: INCONCLUSIVE / HOLD**

No repository workflow or test change was made.
