# ADR-026 — AX Execution Backend for JAMP

**Status:** PROPOSED / DESIGN-ONLY  
**Date:** 2026-09-25  
**Scope:** architecture only; no runtime implementation

## Context

JAMP separates AI observation from evidence verification, provenance, conflict handling, and arbitration. Google AX is an external execution/orchestration system for sandboxed agent workloads, with Task, Workspace, Gateway, Model, lifecycle, Git/MCP/skills, and high-throughput controller infrastructure.

JAMP may eventually need a scalable execution substrate for Multi-AI Federation and Experiment Engine workloads. AX is therefore evaluated as an optional execution provider, not as an epistemic authority.

## Decision

AX MAY be integrated as an **optional external execution backend** behind a JAMP adapter.

AX MUST NOT become:

- a source of truth;
- an authority for JAMP Evidence or Arbitration;
- a dependency of the Frozen Core;
- a reason to modify `src/jamp/run.py`.

The integration boundary is:

```
JAMP Research / Experiment layer
        |
        v
    AX Adapter
        |
        v
  AX execution substrate
```

The adapter converts a JAMP execution contract into an AX Task and converts AX lifecycle/execution observations back into JAMP evidence candidates.

## Frozen Core invariant

The Frozen Core remains locked:

- file: `src/jamp/run.py`
- locked blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- required invariant: `Δ(src/jamp/run.py) = 0`

This ADR contains no runtime import, API change, dependency, or workflow modification.

## Boundary contract

### JAMP → AX

The adapter may provide:

- experiment_id;
- task_id;
- immutable repository + commit SHA;
- execution contract digest;
- workspace specification;
- MCP specification/digest;
- skills specification/digest;
- model/provider identity;
- network policy;
- resource limits.

### AX → JAMP

The adapter may return observations containing:

- ax_task_id;
- execution_id;
- lifecycle/status observations;
- workspace readiness;
- gateway/policy identity;
- execution timestamps;
- environment identity;
- output/artifact digests;
- AX event/status evidence.

AX output is **observation**, not verified truth.

## Provenance Contract v0

A minimum execution-evidence envelope is:

```
AXExecutionEvidence {
    experiment_id
    task_id
    ax_task_id

    repository
    commit_sha

    workspace_digest
    mcp_config_digest
    skills_digest
    gateway_policy_digest

    model_id
    model_config_digest

    execution_contract_digest

    started_at
    completed_at

    output_digest
    artifact_digests[]

    ax_event_digest
}
```

Every digest MUST bind the recorded identity to the execution being reported. Mutable branch names MUST NOT substitute for immutable commit identity.

Execution evidence does not establish the truth of the agent's output.

## Threat model

| Threat | Required JAMP treatment |
|---|---|
| Agent fabricates a result | Keep as observation until independently verified |
| Mutable Git reference | Require immutable commit SHA |
| MCP configuration drift | Record configuration digest |
| Skill drift | Record skills digest |
| Network-policy drift | Record gateway policy identity/digest |
| Model substitution | Record model identity/configuration |
| Task identity confusion | Bind AX task ID to JAMP execution ID |
| Workspace mutation | Record relevant before/after digests |
| Missing execution evidence | Fail closed as INCONCLUSIVE |
| Conflicting lifecycle/output evidence | Preserve CONFLICT; do not synthesize PASS |
| AX unavailable | Execution becomes INCONCLUSIVE, not PASS |
| AX protocol change | Pin/record adapter and provider versions |

A declared network allowlist is evidence of the declared policy, not proof that network escape is impossible.

Likewise, an orchestration success status MUST NOT by itself establish command-level success.

## Failure semantics

The adapter MUST preserve JAMP fail-closed semantics:

```
missing task evidence       -> INCONCLUSIVE
missing provenance          -> INCONCLUSIVE
conflicting execution data  -> CONFLICT
unverified agent output     -> OBSERVATION ONLY
AX unavailable              -> INCONCLUSIVE
```

No synthetic PASS may be generated from AX status alone.

## Non-goals

This ADR does not:

- add AX as a dependency;
- add Kubernetes/AX runtime code;
- modify `src/jamp/run.py`;
- change experiment contracts;
- change CI workflows;
- define production deployment;
- grant AX arbitration authority;
- assert AX production readiness.

## Implementation boundary

Any future implementation MUST live outside the Frozen Core and MUST first define:

1. immutable execution identity;
2. provenance binding;
3. evidence ingestion format;
4. independent verification;
5. replay semantics;
6. failure/INCONCLUSIVE behavior;
7. provider/version pinning.

Implementation requires a separate decision/PR and does not follow automatically from this ADR.

## Verification requirements for this ADR

The design-only PR MUST verify:

```
Δ(src/jamp/run.py) = 0
blob(src/jamp/run.py)
  = 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a
```

CI results MUST be treated separately from this architectural decision. A PR-level GREEN result does not constitute post-merge GREEN evidence.

## References

- Google AX repository: https://github.com/google/ax
- AX concepts: https://github.com/google/ax/blob/main/docs/concepts.md
- AX design: https://github.com/google/ax/blob/main/DESIGN.md
- AX runner: https://github.com/google/ax/blob/main/docs/runner.md
