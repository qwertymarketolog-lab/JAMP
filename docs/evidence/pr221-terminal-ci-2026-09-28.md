## PR-scope terminal CI evidence — 2026-09-28

HEAD: `6da23cc6792a3922ba7cdb9b3b4e01c36a6a7af1`

PR: #221

### pull_request scope

Nine `pull_request` workflow runs reached terminal `success`:

| Workflow | Run ID | Conclusion |
|---|---:|---|
| Research Loop v0 Gate | `36446187884` | success |
| EXP-19 Performance Diagnostic | `36446187994` | success |
| P20.11 Diagnostic | `36446187968` | success |
| P20.5 Hypothesis Lifecycle Diagnostic | `36446188138` | success |
| SBOM | `36446188324` | success |
| EXP-18 Field Alignment Diagnostic | `36446188407` | success |
| P23.0-B Cold Replay Diagnostic | `36446188630` | success |
| EXP-21 Phase 2 Scheduling | `36446188146` | success |
| Developer Quality | `36446188277` | success |

All are `event=pull_request`, HEAD `6da23cc...`, PR #221.

### push-scope anomaly on the same HEAD

These are separate `push` runs and must not be counted as PR CI:

- `test.yml`: Run `36446183625`, `failure`, Jobs API `total_count=0`, `jobs=[]`.
- `import-historical.yml`: Run `36446182375`, `failure`; Jobs API has one Job:
  - Job `109009147349`
  - `G1 Trusted Lineage`
  - `completed/success`
  - `15:47:19Z`

### Combined status

Commit status endpoint for HEAD returns:

- `state=pending`
- `total_count=0`
- `statuses=[]`

Therefore this evidence does **not** establish that all required branch-protection checks are satisfied. PR #221 is not declared GREEN.

### Classification

- OBSERVED: 9 PR-scope workflows terminal success.
- VERIFIED: exact Run IDs, events, conclusions, and HEAD SHA above.
- OBSERVED separately: 2 push-scope workflow failures on the same SHA.
- UNKNOWN: required-check satisfaction / final merge gate because combined status is pending with zero statuses and direct check-run enumeration is unavailable.
- ROOT CAUSE = UNRESOLVED.
- STATE = INCONCLUSIVE / HOLD.

No repository changes were made after commit `6da23cc...` during this audit.
