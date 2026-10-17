# JAMP Daily Evidence Agent v0.1

## Decision and scope

This is a bounded, read-only GitHub/CI observer with an Anthropic-generated report. The workflow is **manual-only** (workflow_dispatch). Do not add a schedule trigger until the secret-backed manual run has been inspected and accepted.

The agent may read repository, open PR, Actions run/job, and artifact metadata. It cannot push commits, create PRs, edit issues, merge, or change repository settings. The report is an observation aid, not a JAMP gate or source of truth.

## Runtime inputs

Configure after this PR is reviewed and merged:

- Repository Actions secret ANTHROPIC_API_KEY.
- Repository Actions variable ANTHROPIC_MODEL, set to a model ID enabled for the account.
- GITHUB_TOKEN is the per-run GitHub Actions token; do not create or store a PAT for this workflow.

The workflow uses only contents: read, pull-requests: read, and actions: read. It does not post to Slack or another messaging destination; the first version publishes an artifact for manual inspection.

## Collection

Each manual run captures:

- main commit SHA and src/jamp/run.py blob SHA;
- open PR metadata (number, title, update time, URL, draft flag, head/base SHA);
- up to 15 recent Actions runs, each with workflow/run ID, event, head SHA, status/conclusion, jobs, step status/conclusion, and artifact names;
- explicit zero_jobs_anomaly when a run has no jobs.

The Frozen Core blob must equal 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a. A mismatch is HOLD/failure, not a reason to edit the Core.

## Memory and deduplication

The workflow stores a compact state.json in the jamp-daily-evidence-state Actions artifact (90-day retention). It tracks PR number → updated_at and run ID/attempt → updated_at. A later report labels changed/new snapshots using these identities.

- First-ever run: INITIAL_BASELINE; novelty is unknown, not asserted.
- Existing workflow history but no state artifact: HOLD; do not silently reset memory.
- Corrupt/unsupported state artifact: HOLD.
- State is bounded by artifact retention; long gaps beyond retention require explicit re-baselining.
- State is uploaded only after a successful collection and summary. Reports/evidence are uploaded even when the job fails, when files exist.

## Fail-closed rules

- Source/API error, malformed response, missing required configuration, Anthropic error, or missing prior state with earlier workflow runs => HOLD/BLOCKED and non-zero job result.
- Missing jobs is an anomaly; it is never a test PASS.
- PR CI and post-merge main CI remain distinct.
- No causal diagnosis from status alone.
- Anthropic output is a summary of supplied observations only. The raw structured snapshot remains in evidence.json; model prose is not itself evidence.
- No new/updated event is claimed on the initial baseline.
- The workflow has no schedule trigger and no notification integration in v0.1.

## Manual acceptance sequence

1. Review the PR changed-file list and verify Frozen Core delta = 0.
2. Merge only after terminal PR CI evidence and the required review.
3. Set ANTHROPIC_API_KEY and ANTHROPIC_MODEL in repository settings.
4. Run JAMP Daily Evidence Agent manually once.
5. Inspect Run → Job → jamp-daily-evidence-report artifact; verify main SHA, Frozen Core blob, run/job evidence, zero-job handling, and INITIAL_BASELINE.
6. Run it manually a second time to verify state restoration and deduplication.
7. Only after both runs are inspected, propose a separate minimal change enabling daily schedule. Do not enable schedule in this PR.

## Artifact contents

- report.md: concise Russian summary, with explicit state and boundaries.
- evidence.json: structured snapshot and delta.
- state.json: compact deduplication state, uploaded separately only on successful completion.

No credentials are written to artifacts or logs. The Anthropic API receives the structured snapshot (including PR titles and workflow/job metadata) to produce the report.
