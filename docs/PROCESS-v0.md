# JAMP Process v0

Solo-maintainer project. This document records observed practice, not
GitHub configuration, because branch protection reads return 403 through
the integration API.

## Observed reality

- One maintainer (`qwertymarketolog-lab`).
- PRs #463, #470, #471 merged without a formal GitHub APPROVED review.
  This is the observed baseline, not a claim about branch ruleset.
- No independent reviewer available at this time.

## CI is the project gate

Before merging any PR, verify all of the following on the PR HEAD:

- **Run Pytest** — partition must equal current baseline + expected delta.
- **Developer Quality** — Ruff check, Ruff format --check, Mypy, baseline integrity.
- **Frozen Core** — `src/jamp/run.py` blob remains
  `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` (Δ = 0).
- **Diff scope** — exactly the files declared in the PR description;
  no drive-by edits.

These are conventions, not enforced by ruleset. A merge without them
is treated as a process incident, recorded as a PR comment.

## Review

- Formal GitHub review is not required while there is one maintainer.
- The audit trail is a PR comment with:
  - HEAD SHA
  - CI run IDs and conclusions
  - partition
  - Frozen Core blob
  - known gaps (e.g., Mypy routing — issue #464)

## Process incidents

- #463 merged without a formal approve. The current integration API read
  of branch protection returns 403, so the ruleset configuration could not
  be independently verified here. Recorded for transparency.
- #470, #471 followed the same practice; no incident.

## Baseline

Current main baseline (update after each post-merge verification):

- Run Pytest: **2086 passed / 1 skipped / 1 deselected**
- Developer Quality: **2074 passed / 13 skipped / 1 deselected**
  (12 PostgreSQL integration + 1 MinIO skip — expected, no
  `JAMP_DATABASE_URL` in that workflow)

Update this section only after a green post-merge run on `main`.

## Known gaps (not blockers for this document)

- Mypy routing bug: `src/jamp/*` changes are not passed to Mypy in
  Developer Quality. Tracked in issue #464.
- `JampVerdict` is created in `/v1/execute` but not persisted with
  the trace. `GET /v1/universal-verdict/{trace_id}` therefore does not
  exist; v0 is a stateless POST. Persistence is a separate track.
- n8n emulator transient failures: issue #469.

## When a second maintainer joins

1. Re-enable branch protection with required review.
2. Require `Run Pytest` and `Developer Quality` as required checks
   (currently required checks are `Research Loop v0 Gate` and
   `G1 Trusted Lineage`).
3. Update this document.
