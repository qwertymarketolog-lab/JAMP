# JAMP Decision Sufficiency Contract v1.1

## Purpose

JAMP-DSC separates **truth verification** from the **decision boundary**.
DECISION_SUFFICIENT means evidence is sufficient for a declared action within a bounded scope; it is not a claim of truth, quality, qualification, or certainty.

## Epistemic states

| State | Meaning | Transition |
|---|---|---|
| UNKNOWN | Evidence is insufficient even for the local decision | BLOCK |
| INCONCLUSIVE | Evidence exists, but a critical conflict or unresolved risk remains | HOLD |
| DECISION_SUFFICIENT | The declared decision gate is satisfied and residual uncertainty is bounded/registered | PROCEED |
| VERIFIED | Final closure is established for the declared scope | CLOSED |

DECISION_SUFFICIENT is a decision-permission state, not a confidence score.

## Sufficiency Gate

A decision may enter DECISION_SUFFICIENT only when all four conditions hold:

1. **Zero Core Violations** — the Frozen Core contract is intact.
2. **Scope Boundedness** — D_scope is explicit and finite for the decision.
3. **Critical Failure Coverage** — all failure modes in the explicit Failure/Threat Model that could invalidate the target action within D_scope are addressed or bounded.
4. **Bounded Residual Uncertainty** — residual uncertainty is explicitly registered in the Residual Uncertainty Register (RUR).

### Scope-relative evidence

The relevant evidence set is:

E_observed(D_scope)

not an unrestricted global evidence pool. Evidence outside D_scope must not silently satisfy the gate.

### Explicit Failure/Threat Model

Critical Failure Coverage is evaluated against an explicitly declared **Failure/Threat Model** for D_scope.

Coverage is complete iff every failure mode in that model that could invalidate the target action is either:

- directly evidenced as absent/controlled, or
- explicitly bounded with residual uncertainty recorded in RUR.

## Residual Uncertainty Register

Every DECISION_SUFFICIENT result must preserve an RUR containing, at minimum:

- unresolved item;
- scope affected;
- evidence reference;
- impact on the decision;
- bounding condition / mitigation;
- owner or next observation, when applicable.

Absence of an RUR is not evidence that uncertainty is zero.

## Stop Mechanism

Once the Sufficiency Gate is satisfied for the current D_scope, investigation of unrelated sub-phenomena is an operational error. A new question requires a new D_scope and gate evaluation.

SUFFICIENT != CERTAIN.

## Anti-Inflation Rule

DECISION_SUFFICIENT MUST NOT be used as a synonym for:

- PASS;
- QUALIFIED;
- VERIFIED;
- model quality;
- truth of a research claim.

The state authorizes the **specific declared transition**, not a broader claim.

## Contract-test fixtures

These fixtures are normative desk-test cases for the DSC state machine.

### Fixture 1 — UNKNOWN / BLOCK

**Input**

- D_scope: determine whether an executable CI check ran.
- E_observed(D_scope): workflow run reports conclusion=failure, but jobs=[].
- Failure/Threat Model: executable job did not run / execution evidence absent.
- RUR: cannot bound the missing execution evidence.

**Expected**

UNKNOWN → BLOCK

Reason: no evidence establishes the local execution decision.

### Fixture 2 — INCONCLUSIVE / HOLD

**Input**

- D_scope: determine whether R27 evidence is sufficient for model qualification.
- E_observed(D_scope): terminal runtime job and artifact exist.
- Critical evidence remains unresolved within scope.
- Failure/Threat Model: unresolved mandatory qualification evidence can invalidate qualification.
- RUR: unresolved qualification item is recorded.

**Expected**

INCONCLUSIVE → HOLD

Reason: evidence exists, but a critical decision-blocking uncertainty remains.

### Fixture 3 — DECISION_SUFFICIENT / PROCEED

**Input**

- D_scope: verify a docs-only change preserves the Frozen Core and satisfies its documentation gate.
- E_observed(D_scope): exact Frozen Core blob matches; changed-file scope is docs-only; declared Failure/Threat Model covers core mutation and unintended non-doc changes; all modeled failure modes are addressed/bounded; RUR records residual non-blocking uncertainty.
- Core delta: 0.
- No runtime behavior claim is made.

**Expected**

DECISION_SUFFICIENT → PROCEED

Reason: the evidence satisfies the declared decision boundary without inflating the result into a general repository PASS.

## Invariants

- UNKNOWN cannot be upgraded by absence of contrary evidence.
- INCONCLUSIVE cannot be upgraded merely because CI is green if the decision-critical evidence remains unresolved.
- DECISION_SUFFICIENT is always relative to D_scope.
- VERIFIED is always relative to the declared scope and closure criteria.
- Frozen Core changes require a separate explicit Core Unlock decision.
