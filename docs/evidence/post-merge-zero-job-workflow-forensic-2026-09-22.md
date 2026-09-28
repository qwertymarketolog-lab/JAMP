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

## Terminal CI snapshot for documentation commit

Documentation commit: `fb0aa977b3e6b508a40bd98073da16a07935540c`.

All eight push-triggered workflow runs for this commit reached terminal state:

| Workflow | Run ID | Job ID | Conclusion | Scope |
|---|---:|---:|---|---|
| Developer Quality | `35778668186` | `106918248196` | success | post-merge main push |
| P20.5 Hypothesis Lifecycle Diagnostic | `35778667974` | `106918247434` | success | post-merge main push |
| P20.11 Diagnostic | `35778668082` | `106918247758` | success | post-merge main push |
| SBOM | `35778668022` | `106918247544` | success | post-merge main push |
| EXP-19 Performance Diagnostic | `35778668078` | `106918247530` | success | post-merge main push |
| P23.0-B Cold Replay Diagnostic | `35778667949` | `106918246568` | success | post-merge main push |
| `.github/workflows/test.yml` | `35778666431` | none | failure | zero-job workflow-level result |
| `.github/workflows/import-historical.yml` | `35778665306` | none | failure | zero-job workflow-level result |

For the last two runs, the GitHub jobs endpoint returned `total_count=0` and `jobs=[]`.

Therefore the terminal evidence does not justify a GREEN post-merge verdict. The state remains:

**Post-merge main: INCONCLUSIVE / HOLD**

**ROOT CAUSE = UNRESOLVED**

This snapshot records terminal evidence only; it does not claim that the two zero-job failures are test failures.

## Final forensic matrix

This matrix closes the current evidence collection step without closing the underlying root-cause investigation.

| Main commit | 1st zero-job run | 1st workflow | 2nd zero-job run | 2nd workflow | Jobs for both | Normal workflows on same push |
|---|---:|---|---:|---|---|---|
| `cb9dc767b0294d30c042a40c72a6503dab31a85e` | `35776095200` | `import-historical.yml` | `35776096278` | `test.yml` | `[]` / `[]` | materialized and successful |
| `fb0aa977b3e6b508a40bd98073da16a07935540c` | `35778665306` | `import-historical.yml` | `35778666431` | `test.yml` | `[]` / `[]` | materialized and successful |
| `7bd89b24272fef107da01503abe2d5bf8130febc` | `35779045627` | `import-historical.yml` | `35779047632` | `test.yml` | `[]` / `[]` | materialized and successful |

For all six listed zero-job runs, the exact workflow-jobs endpoint returned `total_count=0` and `jobs=[]`. The first/second ordering is therefore stable across three consecutive `main` commits and is not unique to PR #147.

### Final evidence classification

- **OBSERVED:** the same ordered pair of zero-job workflow failures recurs on three consecutive `main` commits.
- **VERIFIED:** exact run IDs, workflow identities, and zero-job results for all six runs; normal workflows on the same pushes materialized jobs and succeeded.
- **INFERRED:** the anomaly is upstream of ordinary job execution and is consistent with workflow/check-suite materialization behavior.
- **UNKNOWN:** the exact internal GitHub Actions mechanism that produces `failure` with zero jobs; the underlying causal mechanism remains unproven.

**ROOT CAUSE = UNRESOLVED**

**Post-merge main: INCONCLUSIVE / HOLD**

No workflow, test, threshold, provenance identity, or Frozen Core change is authorized by this forensic record.


## Historical revision-boundary qualification — 2026-09-08

A separate historical sequence isolates a deterministic `test.yml` job-materialization boundary. This evidence qualifies the historical zero-job pattern; it does **not** by itself resolve the later post-merge `main` anomaly documented above.

| Run | Run ID | Event | Head SHA | Workflow blob | Job-level `if:` | Jobs |
|---|---:|---|---|---|---|---:|
| #53 | `34275319555` | push | `61bf75e3…` | `4ea1ef03…` | PRESENT | 0 |
| #54 | `34275476428` | push | `ee44d03e…` | `b6e78354…` | ABSENT | 1 |
| #55 | `34275496802` | pull_request | `ee44d03e…` | `b6e78354…` | ABSENT | 1 |
| #56 | `34275733930` | push | `11456299…` | `b6e78354…` | ABSENT | 1 |
| #57 | `34275739843` | pull_request | `11456299…` | `b6e78354…` | ABSENT | 1 |
| #58 | `34279927291` | push | `20f390d1…` | `4ea1ef03…` | PRESENT | 0 |

The workflow blob `4ea1ef03…` contains a job-level `if:` condition requiring a pull-request event or the historical-import commit-message prefix. The `b6e78354…` revision removes that condition and retains `runs-on: ubuntu-latest`, producing one materialized `test` job for both push and pull-request events in #54–#57.

### Check Suite evidence qualification

The workflow-run metadata directly identifies Check Suite IDs:

- #53 → `92852116876`
- #54 → `92852557011`
- #58 → `92864964863`
- #55–#57 → corresponding run Check Suite IDs in their run metadata.

The available GitHub connector exposed the run metadata and job endpoints, but did not expose the Check Suite resource itself for direct retrieval. Therefore **Check Suite status is UNKNOWN / not independently VERIFIED here**. The run-level `conclusion` must not be substituted for direct Check Suite status.

### Evidence classification

- **OBSERVED:** #53 and #58 have zero materialized jobs; #54–#57 have one materialized `test` job.
- **VERIFIED:** the workflow-file revisions and job materialization differ exactly at the #53→#54 and #57→#58 transitions.
- **INFERRED:** the job-level condition explains the zero-job behavior for historical non-PR push cases where the condition evaluates false.
- **UNKNOWN:** direct Check Suite status for #53–#58; this record does not infer it from run conclusion.

**Historical revision-boundary finding: VERIFIED.**

**Current post-merge main root cause: remains UNRESOLVED.**
