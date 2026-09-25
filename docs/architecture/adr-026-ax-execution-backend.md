# ADR-026 — Google AX as an Execution Substrate for JAMP

**Status:** PROPOSED / DESIGN-ONLY  
**Date:** 2026-09-25  
**Target:** JAMP Multi-AI Federation / Experiment Engine  
**Trust boundary:** DESIGNED — non-invasive adapter topology

## 1. Context

JAMP separates AI observation from evidence verification, provenance, conflict handling, arbitration, and replay.

Google AX is evaluated as an **optional external execution substrate** for high-throughput agent workloads. AX and JAMP solve different problems:

- **AX:** task execution, sandbox/workspace orchestration, lifecycle, networking constraints, and scalable scheduling.
- **JAMP:** evidence, provenance, verification, conflict preservation, arbitration, and fail-closed epistemic state.

AX MUST therefore remain outside JAMP's epistemic authority boundary.

## 2. Decision

AX MAY be integrated through an out-of-core adapter:

```
JAMP Research / Experiment layer
              |
              v
          AX Adapter
              |
              v
       Google AX substrate
```

AX telemetry, status, logs, and agent outputs are **observations**, not truth.

The adapter MUST NOT modify the Frozen Core or grant AX authority over JAMP state, Evidence, Provenance, Conflict, or Arbitration.

## 3. Frozen Core invariant

The currently locked invariant is:

- file: `src/jamp/run.py`
- locked blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- required invariant: `Δ(src/jamp/run.py) = 0`

This ADR introduces no runtime import, dependency, workflow change, or modification to `src/jamp/run.py`.

**Scope note:** other JAMP state-machine files are not declared Frozen Core by this ADR unless separately verified. No claim of `Δ(.agents/runner/state_machine.py)=0` is made here.

## 4. Boundary contract

### JAMP → AX

A future adapter MAY provide:

- experiment/task identity;
- immutable repository + commit SHA;
- execution-contract digest;
- workspace specification;
- MCP specification/digest;
- skills specification/digest;
- model/provider identity;
- declared network policy;
- resource limits.

### AX → JAMP

The adapter MAY return execution observations containing:

- AX task/execution identity;
- lifecycle/status observations;
- workspace readiness;
- declared gateway/policy identity;
- execution timestamps;
- environment identity;
- output/artifact digests;
- AX event/status evidence.

These fields describe execution context. They do not establish correctness of the agent's claims.

## 5. Provenance Contract v0

A future execution-evidence envelope SHOULD contain:

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

Immutable commit identity MUST be preferred over mutable branch names.

**Design requirement:** every digest must bind recorded identity to the execution being reported.

**Unknown:** whether current AX exposes all required immutable provenance material directly. This requires implementation-time verification against the pinned AX version.

## 6. Threat model

| Threat | JAMP boundary treatment |
|---|---|
| Agent fabricates a result | Keep output as observation until independently verified |
| Mutable Git reference | Require immutable commit SHA |
| MCP configuration drift | Record and verify configuration digest |
| Skill drift | Record and verify skills digest |
| Network-policy drift | Record declared gateway policy identity/digest |
| Task identity confusion | Bind AX task identity to JAMP execution identity |
| Workspace mutation | Require independently verifiable artifact/tree evidence |
| Missing execution evidence | Fail closed as INCONCLUSIVE |
| Conflicting lifecycle/output evidence | Preserve CONFLICT; no synthetic PASS |
| AX unavailable | INCONCLUSIVE |
| AX protocol/schema change | Strict adapter/schema validation; fail closed |

### Security claims deliberately not assumed

The following are **DESIGN REQUIREMENTS / UNKNOWN**, not verified AX capabilities:

- cryptographically signed AX event streams;
- cryptographic execution tokens;
- proof that Gateway enforcement prevents all egress bypass;
- proof that AX-reported command status equals independently observed process exit status;
- availability of complete filesystem digests inside AX output;
- availability of immutable MCP/skills materialization proofs.

A future adapter MUST establish evidence for these requirements or downgrade the affected observation to INCONCLUSIVE.

## 7. Observation schema

A future adapter MAY use an observation structure equivalent to:

```
JAMP_AX_Execution_Observation {
    observation_id
    timestamp
    ax_task_id
    execution_status

    workspace_lineage {
        git_repository
        git_commit_sha
        mcp_manifest_hash
        skills_bundle_hash
    }

    gateway_policy {
        allowlist_hash
        blocked_attempts_count
    }

    model_configuration {
        provider
        model_name
        parameters_digest
    }

    artifacts_digest[]
}
```

This is a **design contract**, not a claim that current AX already emits every field.

Validation failure MUST produce INCONCLUSIVE rather than a synthetic successful observation.

## 8. Trust and verification boundary

```
AX sandbox
    |
    v
AX controller / event stream
    |
    v
JAMP AX Adapter
    |
    +--> independent identity/provenance checks
    |
    v
JAMP Evidence / Conflict / Arbitration
```

A declared AX policy is evidence of the declared policy, not proof that the policy cannot be bypassed.

Likewise:

```
AX status = COMPLETED
        !=
verified experiment result
```

Independent verification remains a JAMP responsibility.

## 9. Failure semantics

```
missing task evidence       -> INCONCLUSIVE
missing provenance          -> INCONCLUSIVE
provenance mismatch         -> INCONCLUSIVE
conflicting execution data -> CONFLICT
unverified agent output     -> OBSERVATION ONLY
AX unavailable              -> INCONCLUSIVE
schema/protocol mismatch    -> INCONCLUSIVE
```

No AX status may directly generate a JAMP PASS.

## 10. Implementation boundary

Any future implementation MUST remain outside the Frozen Core.

A future adapter is conceptually limited to an out-of-core surface such as:

```
.agents/adapters/ax_adapter.py
.agents/adapters/test_ax_adapter.py
```

Exact paths are **design proposals**, not an already-approved mutation whitelist.

Any future implementation PR MUST separately verify:

1. immutable execution identity;
2. provenance binding;
3. evidence ingestion;
4. independent verification;
5. replay semantics;
6. fail-closed behavior;
7. provider/version pinning;
8. Frozen Core preservation.

No runtime implementation follows automatically from this ADR.

## 11. Non-goals

This ADR does not:

- add AX as a dependency;
- add Kubernetes/AX runtime code;
- modify `src/jamp/run.py`;
- modify existing experiment contracts;
- modify CI workflows;
- define production deployment;
- grant AX arbitration authority;
- assert AX production readiness.

## 12. Consequences

### Positive

- scalable external execution option for future federation/experiments;
- clear separation between execution and epistemic verification;
- no Frozen Core dependency;
- interchangeable execution-provider model.

### Costs / risks

- AX API/protocol evolution requires adapter maintenance;
- execution evidence requires independent verification;
- provenance capture may add overhead;
- AX infrastructure introduces operational dependencies if adopted.

## 13. Verification status

**OBSERVED / VERIFIED**

- JAMP Frozen Core target remains `src/jamp/run.py` blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
- This ADR is documentation-only.
- No runtime implementation is introduced by this PR.

**DESIGN**

- AX is treated as an optional execution backend.
- AX output is observation input, not epistemic authority.
- Provenance and verification remain JAMP responsibilities.

**UNKNOWN**

- whether a pinned AX release currently exposes every provenance field required by this contract;
- whether AX provides cryptographic guarantees for every threat listed above;
- production suitability/stability of AX for JAMP.

## 14. References

- Google AX: https://github.com/google/ax
- AX concepts: https://github.com/google/ax/blob/main/docs/concepts.md
- AX design: https://github.com/google/ax/blob/main/DESIGN.md
- AX runner: https://github.com/google/ax/blob/main/docs/runner.md
