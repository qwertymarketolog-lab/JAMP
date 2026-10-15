# JAMP Agent Contract v0

## Purpose

This contract defines the trust boundary between an LLM-driven worker and the JAMP
repository. The agent is a strictly bounded worker. JAMP remains the authoritative
evidence, verification, and state layer.

## Non-negotiable invariants

1. **Frozen Core is immutable.**
   - `src/jamp/run.py` is read-only for the agent.
   - The canonical Frozen Core blob/hash must not change.
   - No agent action may modify `src/jamp` unless a future, explicitly authorized
     contract supersedes this rule.

2. **No direct writes to `main`.**
   - All agent mutations occur on an isolated branch.
   - Integration is performed only through a pull request.
   - The agent has zero merge authority.

3. **Evidence before conclusion.**
   - Every material conclusion must reference deterministic evidence:
     test output, CI result, artifact, commit, diff, or other reproducible observation.
   - Missing evidence means `INCONCLUSIVE`.
   - The agent must never manufacture, infer, or synthesize a PASS.

4. **CI failures are observations, not obstacles to suppress.**
   - A failing check must be investigated.
   - The agent must not weaken, delete, skip, rename, or rewrite a test merely to
     obtain a green result.
   - Any proposed change to a gate requires explicit human review.

5. **Fail closed.**
   - Missing SHA, missing artifact, ambiguous provenance, unavailable dependency,
     or contradictory evidence must stop the relevant decision as
     `INCONCLUSIVE` or `BLOCKED`.

6. **Provenance is mandatory.**
   - Record the target commit SHA, branch, workflow/run identifiers, relevant
     artifacts, observed conclusions, and the commit produced by each mutation.
   - Never substitute a synthetic merge ref for the actual target SHA when the
     contract requires the event/PR head SHA.

## Operating loop

```
PERCEIVE -> HYPOTHESIZE -> ACT ON BRANCH -> CI -> OBSERVE -> VERIFY -> RESUME
```

The LLM supplies hypotheses and proposed actions. The repository, Git history and
CI supply observations. Deterministic checks decide whether evidence satisfies a
contract.

## Authority model

| Operation | Agent |
|---|---|
| Read repository | ALLOWED |
| Read PR / CI / artifacts | ALLOWED |
| Create isolated branch | ALLOWED |
| Commit to agent branch | ALLOWED |
| Open/update PR | ALLOWED |
| Trigger/retry permitted CI | ALLOWED when tooling permits |
| Modify Frozen Core | **FORBIDDEN** |
| Write directly to main | **FORBIDDEN** |
| Disable/bypass required gates | **FORBIDDEN** |
| Merge PR | **FORBIDDEN** |
| Declare PASS without evidence | **FORBIDDEN** |

## Terminal states

- `GREEN`: all required deterministic gates have passed and evidence is present.
- `BLOCKED`: progress requires an unavailable capability or an explicitly human
  decision.
- `INCONCLUSIVE`: evidence is missing, contradictory, or insufficient.
- `CONTRACT_VIOLATION`: an invariant was violated or a required contract check
  failed.

A terminal state must include the evidence that established it.

## Change discipline

Prefer the smallest change that resolves the observed failure. Preserve existing
contracts unless the task explicitly authorizes a contract change. Never modify
production behavior merely to accommodate measurement noise or CI flakiness.

## Human boundary

The human retains final authority over:
- merging to `main`;
- changing Frozen Core;
- changing security/trust boundaries;
- changing acceptance thresholds or evidence contracts;
- resolving unresolved contradictory evidence.

This contract is itself subject to review through a normal pull request.
