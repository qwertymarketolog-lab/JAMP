# Autonomous Research Loop v0

TASK -> AGENT -> GITHUB -> PR -> CI -> EVIDENCE -> STATE

The agent executes bounded tasks; it is not an authority on truth.

Agent may:
- read repository state and task contracts;
- form hypotheses;
- modify only task-allowed paths;
- create branches, commits and PRs;
- collect CI, job and artifact evidence;
- return observations to the deterministic gate.

Agent must not:
- modify src/jamp/run.py;
- weaken tests, thresholds, workflow protections or task scope;
- treat missing jobs as PASS;
- treat PR CI as post-merge main CI;
- merge or claim success without terminal evidence;
- fabricate CI, artifact, provenance or causal evidence.

Fail closed:
- missing or contradictory evidence => INCONCLUSIVE;
- failed terminal CI => FAILED;
- path violation => REJECT;
- Frozen Core blob mismatch => REJECT;
- non-terminal CI => HOLD;
- jobs=[] => no PASS and no inferred test result.

State machine:
OPEN -> RUNNING -> AWAIT_CI -> VERIFIED -> CLOSED

Failure or incomplete evidence may move to FAILED, INCONCLUSIVE or HOLD.
Every transition requires explicit evidence.

Merge authority remains outside the agent loop.

Every CI assertion records commit SHA, workflow, run ID, job ID, status, conclusion, artifact/output when present, and scope (PR or post-merge main).
source_sha and target_sha are bound to the exact task execution.
