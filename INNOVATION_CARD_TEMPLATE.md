# Innovation Card — Template

> Copy this file to `INNOVATION_CARD.md` in the owning `ji-0X-*` branch.
> A branch without its completed card is **INACTIVE** and must not start implementation work.

## 1. Identity and ownership

- **Code:** `JI-XX`
- **Direction:**
- **Branch:**
- **Accountable owner (GitHub login):** `UNASSIGNED` until explicitly accepted
- **Contributors:**
- **Created / last reviewed (UTC):**
- **Status:** `PROPOSED | ACTIVE | BLOCKED | HOLD | COMPLETE | REJECTED`

No owner is implied by a branch name, commit author, or reviewer. The accountable owner must explicitly accept responsibility.

## 2. Hypothesis

State one falsifiable engineering hypothesis.

- **Claim:**
- **Intended operating environment and use case:**
- **Out of scope:**
- **What observation would disprove the hypothesis?**

Do not present a target, aspiration, simulation assumption, or model output as an observed result.

## 3. Technical feasibility

Describe the proposed mechanism and its constraints.

- **System boundary:**
- **Required inputs / outputs:**
- **Dependencies and interfaces:**
- **Physical, computational, operational constraints:**
- **Standards / regulatory constraints (jurisdiction and edition):**
- **Known unknowns:**

Separate established facts, design assumptions, estimates, and unresolved questions.

## 4. Evidence

List each evidence item using the evidence record convention in `evidence/README.md`.

| Evidence ID | Claim supported | Source / artifact | Method and conditions | Integrity identifier | Classification | Limitations |
|---|---|---|---|---|---|---|
| E-001 | | | | | `RAW / DERIVED / EXTERNAL / SIMULATED` | |

Evidence status: `NOT_COLLECTED | INCOMPLETE | REVIEWED | CONTRADICTED`.

A hash establishes byte identity only; it does not establish source authenticity, measurement validity, or truth. Missing evidence is `UNKNOWN`, not a negative finding.

## 5. Technology Readiness Level (TRL)

- **Proposed TRL (1–9):** `UNKNOWN` until assessed
- **Assessment framework / source:**
- **Evidence supporting this level:**
- **Evidence gaps:**
- **Independent reviewer and date:**

State the exact TRL framework used. Do not infer a TRL from project maturity, a roadmap, or a successful isolated test. If evidence is insufficient, retain `UNKNOWN`.

## 6. Risks and hazards

| ID | Hazard / risk | Cause and consequence | Severity / likelihood method | Mitigation | Residual risk | Evidence |
|---|---|---|---|---|---|---|
| R-001 | | | | | | |

Include foreseeable misuse, environmental limits, failure modes, human factors, cybersecurity, supply chain, maintenance, and regulatory risks where relevant. High-consequence safety claims require qualified review and appropriate standards-based testing.

## 7. Proof of Concept (PoC) plan

- **Question the PoC answers:**
- **Prototype / simulation / test-stand boundary:**
- **Inputs, assumptions, and parameter sources:**
- **Method and reproducible procedure:**
- **Instrumentation and raw data capture:**
- **Safety controls and stop conditions:**
- **Expected outputs (not pre-declared results):**
- **Reproduction instructions:**

A simulation demonstrates behavior only within its model and assumptions. It is not field, human-subject, certification, or operational validation.

## 8. Acceptance criteria

Define measurable, falsifiable criteria before running the PoC.

| ID | Criterion | Measurement method | Threshold / expected range | Evidence required | Result |
|---|---|---|---|---|---|
| AC-01 | | | | | `NOT_RUN` |

Allowed result values: `PASS | FAIL | INCONCLUSIVE | NOT_RUN`. Explain deviations. Do not convert missing or ambiguous data into PASS.

## 9. Review and decision log

| Date (UTC) | Reviewer | Scope reviewed | Decision | Evidence / rationale | Follow-up |
|---|---|---|---|---|---|
| | | | `APPROVE | REQUEST_CHANGES | HOLD` | | |

## 10. Integration gate

- **PoC completed and independently reviewed:** `NO`
- **TRL ≥ 6 substantiated:** `NO / UNKNOWN`
- **Regression evidence available:** `NO`
- **Gate review completed:** `NO`
- **Separate written authorization to merge into main:** `NO`

No item above is satisfied by this template. Merge into the main JAMP branch remains prohibited until every D-04 gate is independently evidenced and separate written authorization is recorded.
