---
applyTo: ".github/workflows/**,scripts/**,tests/**"
---

# CI and Test Evidence Contract

## GitHub Actions terminal evidence

Do not claim a workflow or check is VERIFIED SUCCESS unless the following chain has been inspected from GitHub for the exact commit under discussion:

- Commit SHA;
- Workflow name and Run ID;
- Job ID, job name, and terminal Conclusion;
- Artifact ID and artifact name belonging to that Run ID.

The run and job must be terminal. Pending/in-progress runs are RUNNING. Missing run/job/log/artifact evidence is UNKNOWN or HOLD, never PASS. An empty `jobs=[]` response is not success. A PR run does not prove post-merge behavior on `main`; inspect the post-merge commit separately.

If the workflow does not upload an artifact, report the GitHub conclusion as OBSERVED but classify the evidence package as **INCOMPLETE — ARTIFACT MISSING**. Do not invent an Artifact ID or describe that evidence as VERIFIED. Where a workflow is intended to provide terminal evidence, retain useful raw logs and upload them with the repository's approved artifact mechanism.

## Local tests

Local execution is not GitHub Actions CI. When reporting local results, retain:
- exact command and working directory;
- relevant runtime/tool versions and environment constraints;
- complete relevant stdout/stderr or durable log;
- process exit code.

A statement such as "tests passed locally" without command, logs, and exit code is not evidence. Even with those records, label the result LOCAL / OBSERVED (or verified only for the precise local behavior exercised); never substitute it for terminal GitHub CI.

## Failure handling

- Do not infer success from a green badge alone; inspect Run → Job → Conclusion and artifact.
- Do not treat skipped, cancelled, timed-out, neutral, or missing jobs as success.
- Preserve contradictory statuses as AMBIGUOUS and investigate their provenance.
- Do not hide failures, suppress exceptions, delete tests, weaken assertions, change thresholds, disable Ruff/Mypy, or bypass required checks.
- Establish ROOT CAUSE before modifying code or workflow configuration. If root cause is unresolved, stop and report HOLD.
- A fix must include an appropriate regression test and fresh CI evidence.
- After merge, independently verify post-merge CI on the resulting `main` SHA.
