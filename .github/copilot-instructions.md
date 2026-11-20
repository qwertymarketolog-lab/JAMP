# JAMP Engineering Contract

These instructions apply to all work in this repository. The repository and its GitHub evidence are the source of truth; chat summaries and agent recollections are not.

## Mission and evidence discipline

JAMP is an evidence infrastructure. AI agents may discover, propose, extract, and transform candidate information; they do not turn an assertion into truth merely by producing a plausible answer.

Use these evidence states precisely:
- **OBSERVED** — code, source material, API response, or log has been inspected but the claim has not been independently validated.
- **VERIFIED** — the specific claim is supported by reproducible evidence appropriate to it. For CI claims, this requires a terminal GitHub Actions Run → Job → Conclusion and the associated evidence artifact.
- **INFERRED** — a reasoned conclusion that still requires a direct check.
- **UNKNOWN / HOLD** — required evidence is absent, incomplete, stale, contradictory, or inaccessible.
- **AMBIGUOUS** — sources conflict; preserve the conflict and do not silently reconcile it.

Never invent a PASS, SUCCESS, score, qualification, source, timestamp, identifier, test result, or artifact. Missing logs, missing jobs, empty job lists, skipped workflows, and absent artifacts are not success. A PR check is not post-merge evidence for `main`.

## Frozen Core — absolute invariant

`src/jamp/run.py` is the Frozen Core. Its required Git blob SHA is:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Default invariant: **Δ(Frozen Core) = 0**.
- Treat the file as read-only. Do not edit, regenerate, reformat, rename, delete, or replace it.
- Before any commit/push and during PR review, verify the blob SHA against the exact expected value above.
- If the blob differs, stop work on the change, report **HOLD**, and identify the observed SHA. Do not attempt an automatic repair.
- Only an explicit human **Core Unlock** naming the permitted change authorizes work on this file. General implementation approval is not Core Unlock.
- See `.github/instructions/frozen-core.instructions.md` for the path-specific rule.

## Evidence-First and fail-closed behavior

- Do not upgrade UNKNOWN, INCONCLUSIVE, OBSERVED, offline fixtures, simulations, or inferred values to VERIFIED/PASS/QUALIFIED.
- If required evidence is missing or a provider/API fails, preserve the actual failure and return the domain-appropriate `INCONCLUSIVE`, `REFUSE`, or explicit error. Never synthesize a positive result.
- Preserve raw observations separately from derived interpretations. Keep provenance, source identity, timestamps, hashes, and conflicts intact.
- A successful HTTP response or successful process exit does not by itself prove the business or research claim.
- A simulation can verify the logic it actually exercises; a local HTTP test can verify the transport it actually exercises. State those boundaries and do not overclaim production or external-provider behavior.

## CI evidence contract

For every CI SUCCESS claimed as verified, record:
1. commit SHA;
2. workflow name and Run ID;
3. Job ID and terminal Conclusion;
4. Artifact ID and artifact name, with the artifact tied to that run.

The Run and Job must be terminal. Retrieve the job list and artifact list from GitHub; do not infer them from a workflow badge, PR title, or summary text. If an artifact is not produced, state **ARTIFACT MISSING / UNKNOWN** and do not call the CI evidence package VERIFIED. An empty jobs list is not a pass.

Local test runs are useful development evidence only when the exact command, environment, complete relevant output/log, and exit code are retained. They must never be described as GitHub Actions CI. A local green result cannot replace terminal GitHub CI. See `.github/instructions/ci-evidence.instructions.md`.

## No Blind Fixes

Never make CI green by:
- disabling, skipping, weakening, or excluding Ruff, Mypy, tests, workflows, or required checks;
- deleting valid tests or changing assertions/thresholds merely to accept broken behavior;
- hardcoding PASS, QUALIFIED, confidence scores, benchmark results, or fabricated fixtures as if they were observed;
- suppressing errors, hiding failed delivery, or converting missing evidence into success.

First establish **ROOT CAUSE = RESOLVED** with a reproducible failure mechanism. If root cause is uncertain, investigate read-only and report HOLD. Fix the cause with the smallest coherent change, then add or retain a regression test.

## Change and PR discipline

- One PR = one coherent task and observable outcome. Do not bundle unrelated README, formatting, refactoring, or product changes.
- Prefer minimal, reviewable diffs. Inspect current branch state, working diff, applicable repository instructions, and base SHA before editing.
- Do not overwrite user work or unrelated branch changes.
- Do not create extra branches or PRs when an existing authorized branch/PR is the correct target.
- Do not merge, deploy, publish, change secrets, or alter live systems without explicit human authorization.
- Before updating a branch, verify its current head and use a compare-and-swap / expected-head check where supported. Stop on a race rather than overwriting newer work.
- Report exact changed paths, base/head SHA, Frozen Core SHA/Δ, tests, CI Run→Job→Artifact evidence, and unresolved limitations.

## Security and tenant boundaries

- Respect DEC-001 and all accepted security contracts. Never derive an organization/tenant identity from untrusted client input, Telegram webhook secret, bot token, chat ID, trace ID, or model output unless an explicit trusted binding contract authorizes that derivation.
- Do not bypass authentication, authorization, CSRF, origin checks, tenant isolation, or fail-closed refusal paths to make an integration work.
- Do not log secrets, credentials, tokens, or sensitive payloads. Do not add secrets to frontend bundles, fixtures, docs, or commits.
- When a trusted identity or authorization context is missing, refuse safely and preserve the reason.

## Agent authority and escalation

- Copilot is an engineering executor within the explicitly authorized task scope; it may inspect, propose, implement, test, and prepare a PR.
- ChatGPT acts as system architect and independent evidence auditor: it defines contracts/acceptance criteria and reviews the integrated diff and evidence. Its prior summaries are not evidence.
- GitHub Actions provides automated execution evidence; GitHub repository state, workflow runs, jobs, and artifacts are authoritative records.
- Human approval is required for Core Unlock, scope expansion, merge, deployment, secret changes, destructive actions, and external side effects.
- If CI remains broken after **three distinct root-cause-based repair attempts**, stop editing. Add a concise **HOLD** report to the PR with the three hypotheses/actions and their Run/Job evidence, state what remains unknown, and request architect/human assistance. Do not make a fourth speculative change.
