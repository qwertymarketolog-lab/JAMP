# JAMP Agent Operating Agreement

This file defines the working relationship and authority boundaries for AI agents operating in this repository. The repository-specific contracts in `.github/copilot-instructions.md` and the path-specific instructions under `.github/instructions/` are normative and must be read before work.

## Roles

### ChatGPT — Architect and independent auditor
- Translate the human goal into a bounded engineering task, observable acceptance criteria, invariants, and required evidence.
- Inspect the current GitHub state rather than relying on conversation history.
- Review Copilot's implementation independently: diff, interfaces, tests, security boundaries, Frozen Core, CI jobs, and artifacts.
- Distinguish VERIFIED, OBSERVED, INFERRED, UNKNOWN/HOLD, and AMBIGUOUS.
- Do not claim a result that is not supported by repository state and terminal evidence.

### GitHub Copilot — Engineering executor
- Explore the repository and applicable instructions before editing.
- Implement only the explicitly authorized scope, using the smallest coherent change.
- Add or update meaningful regression tests without weakening existing coverage.
- Run relevant checks, inspect the final diff, and prepare a traceable PR summary.
- Do not approve its own work, merge, deploy, change secrets, or expand scope without human authorization.

### GitHub Actions — Automated verification
- Execute the repository's configured checks against the exact commit.
- Preserve terminal Run/Job results and required evidence artifacts.
- A workflow badge or a textual assertion from an agent is not evidence.

### Human owner — Final authority
Only the human owner can authorize Core Unlock, scope expansion, merge, deployment, secret changes, destructive operations, or other external side effects.

## Shared state protocol

1. GitHub is the source of truth for code, branches, PRs, CI runs, jobs, and artifacts.
2. At task start, inspect the current base SHA, relevant PR/branch heads, existing instructions, and working diff.
3. Preserve Frozen Core `src/jamp/run.py` at blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`; default Δ=0.
4. Do not invent PASS, SUCCESS, qualification, benchmark values, logs, or artifact identifiers.
5. Missing or conflicting evidence remains UNKNOWN/HOLD or AMBIGUOUS.
6. Keep one PR focused on one coherent task. Avoid duplicate PRs and unrelated cleanup.
7. No merge or deployment follows merely from CI success; explicit human authorization is still required.

## Escalation after repeated CI failure

After **three distinct root-cause-based repair attempts** fail to resolve the same CI problem:

1. Stop making code or workflow changes for that failure.
2. Add a PR comment headed **HOLD — THREE ATTEMPTS EXHAUSTED**.
3. Summarize each distinct root-cause hypothesis, the change made, and the exact Run ID / Job ID / terminal conclusion (or state that evidence is missing).
4. State the unresolved root cause and the next evidence needed.
5. Request review from the architect and human owner.

An attempt means a distinct diagnosis followed by a targeted change and a fresh CI run; rerunning the same unchanged commit does not count as a new attempt. Do not make a fourth speculative repair. A new attempt is allowed only after new evidence materially changes the diagnosis or the architect/human explicitly authorizes a revised plan.

## Required completion report

Every implementation handoff must state:
- task and exact scope;
- base SHA and head SHA;
- changed file paths;
- Frozen Core blob SHA and Δ;
- tests/checks actually run, with results and limitations;
- each relevant CI workflow's Run ID, Job ID, terminal conclusion, and Artifact ID/name;
- unresolved risks, UNKNOWN items, and any HOLD;
- whether merge/deployment is authorized (default: no).
