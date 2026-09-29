# JAMP — Execution Preflight Contract

## Purpose

Prevent CI/workflow executions whose required execution inputs have not been verified at the intended checkout SHA.

This contract is a mandatory gate before every GitHub Actions execution, experiment run, probe, or workflow rerun.

## 1. Mandatory preflight

Before execution, verify all of:

- target SHA;
- target branch/ref;
- workflow file;
- workflow trigger;
- checkout SHA/ref;
- executable entrypoint/script;
- required imports/config/fixtures;
- required secrets;
- expected artifact path.

The critical invariant is:

`workflow source` and `checkout SHA` are separate facts and MUST NOT be conflated.

If the workflow checks out `TARGET_SHA`, every required entrypoint and input MUST be proven to exist at `TARGET_SHA` before execution.

If any precondition is unverified:

`STATE = HOLD`

`ROOT CAUSE = PRECONDITION NOT VERIFIED`

Do not launch CI merely to discover a missing file, wrong ref, or missing input.

## 2. Execution graph

Record before launch:

```
Workflow:
Workflow SHA:
Trigger:
Target branch/ref:
Checkout SHA:
Entrypoint:
Entrypoint verified at checkout SHA: YES/NO
Required inputs:
Secrets:
Expected artifact:
```

Execution is permitted only when the execution graph is verified.

## 3. Controlled probes

For a controlled probe, distinguish:

- BASE/TARGET SHA — code state being investigated;
- PROBE CODE SHA — runner/probe code added for measurement;
- WORKFLOW SHA — workflow definition;
- EXECUTION SHA — commit that triggered the run.

If probe code is absent from the target SHA, the run MUST be described as:

`probe derived from TARGET SHA with PROBE CODE SHA`

It MUST NOT be described as execution of the unmodified target SHA.

## 4. Branch/workflow creation

Before creating a workaround branch or workflow:

1. verify whether the required workflow already exists;
2. verify whether the required entrypoint already exists;
3. verify whether the trigger is available;
4. verify the target ref/SHA;
5. identify the exact blocker.

Do not create duplicate workflows or branches to compensate for an unverified precondition.

## 5. Failure protocol

A failed run follows:

`RUN → FAILED STEP → LOG → ROOT CAUSE → MINIMAL FIX → RERUN`

Never:

`FAILURE → BLIND FIX → RERUN`

A CI failure caused by a missing execution precondition is not evidence of application/test failure.

## 6. Terminal evidence

After launch, record:

```
Run ID:
Workflow:
Event:
Branch:
Head SHA:
Checkout SHA:
Job ID:
Status:
Conclusion:
Artifact:
```

Do not declare PASS/GREEN until terminal evidence exists.

## 7. Mandatory state rule

```
PRECONDITION VERIFIED
        ↓
EXECUTE
        ↓
TERMINAL EVIDENCE
        ↓
CONCLUSION
```

If preconditions are not verified:

`HOLD`

The CI system is an execution verifier, not a preflight discovery mechanism.

## 8. Frozen Core

This contract MUST NOT be used as justification for changing:

`src/jamp/run.py`

Frozen Core blob:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Default invariant:

`Δ(src/jamp/run.py) = 0`

