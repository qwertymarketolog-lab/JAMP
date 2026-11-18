# ADR: JAMP Autonomous Research Loop

- **Status:** Proposed
- **Scope:** Agent execution architecture
- **Frozen Core:** Untouched
- **Decision:** Separate persistent JAMP state/evidence from the computational runner.

## Context

JAMP is evidence-first research infrastructure. An LLM can generate useful
hypotheses and execute engineering actions, but its internal state must not become
the authoritative project state. Long-running autonomy therefore needs a strict
trust boundary between:

1. **JAMP repository state** — contracts, task definitions, evidence, provenance,
   deterministic gates, and durable history.
2. **Runner process** — ephemeral compute that invokes an interchangeable LLM,
   reads repository state, performs bounded actions, and resumes from durable
   evidence.

This separation permits long-running autonomous work without treating model memory
or confidence as project truth.

## Decision

Adopt a hybrid autonomous loop:

```
JAMP Contract / State
        |
        v
Runner
        |
        +--> LLM (swappable)
        |
        +--> isolated branch
        |
        +--> commit / PR
        |
        v
GitHub CI / deterministic gates
        |
        v
Evidence + provenance
        |
        v
Runner resume
```

The runner may be implemented initially as GitHub Actions and may later be moved to
a self-hosted runner without changing the JAMP trust contract.

### Wake-up

Supported entry points include `workflow_dispatch`, scheduled execution, and a
future event-driven resume mechanism.

### Perception

The runner reads the agent contract and task queue, then inspects the current PR,
commit ancestry, CI state, logs, and artifacts relevant to the task.

### Hypothesis

The LLM proposes the smallest next action from observed evidence. A proposal is
not itself evidence.

### Execution

The runner applies only contract-permitted mutations on an isolated branch and
records the resulting commit SHA.

### Verification

CI and repository checks provide deterministic observations. The runner must not
reinterpret a failed gate as success.

### Resume

The next invocation resumes from durable repository/CI evidence rather than relying
on hidden model memory.

## Runner choices

### GitHub Actions — initial implementation

Advantages:
- native repository/PR/CI integration;
- transparent run history;
- simple reproducibility;
- no separate infrastructure required for the initial experiment.

Constraint:
- individual jobs have finite execution limits.

Therefore long tasks use checkpoint/resume rather than relying on one uninterrupted
process.

### Self-hosted runner — optional extension

A self-hosted runner can support longer continuous execution and local models.
It remains subordinate to the same repository contract and must treat GitHub/CI as
the source of durable project state.

### External SaaS agent — not the architectural authority

A third-party agent may be used as an interchangeable LLM/worker implementation
only if it can operate within the same trust boundary. It must not become the
source of truth or receive unrestricted merge authority.

## State and evidence requirements

Each autonomous run should preserve, at minimum:

- run identifier;
- task identifier;
- source/target commit SHA;
- branch and PR;
- LLM/model identifier when available;
- proposed action;
- executed action;
- resulting commit SHA;
- CI workflow/run identifiers;
- relevant artifact identifiers;
- deterministic conclusion;
- terminal state.

The durable record belongs to JAMP. The runner's local process state is disposable.

## Safety properties

1. Frozen Core remains immutable.
2. `main` remains outside the agent's direct write path.
3. Every mutation has Git provenance.
4. Every conclusion has evidence or is fail-closed.
5. CI failures trigger investigation, not suppression.
6. Model choice can change without changing the trust contract.
7. Human merge authority remains explicit.

## Initial experiment boundary

The first implementation should be limited to CI/provenance completion work.
It must not automatically merge, alter Frozen Core, change acceptance thresholds,
or redesign deterministic gates.

Success means the agent can repeatedly:

```
observe -> act -> commit -> CI -> observe -> resume
```

while preserving complete provenance and terminating in a contract-defined state.

## Consequences

The architecture deliberately sacrifices unrestricted autonomy in exchange for
auditability and reproducibility. A model can be replaced without changing the
evidence model. A runner can restart without losing authoritative state. A failed
experiment remains a recorded failure rather than being smoothed into a success.

This is consistent with the JAMP principle:

> AI searches and acts; JAMP verifies, decomposes, connects, compares, and preserves
> the evidence history.
