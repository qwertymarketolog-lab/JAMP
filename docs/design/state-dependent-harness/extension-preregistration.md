# Extension Pre-Registration

**Date:** 2026-09-11  
**Status:** SKELETON — SELECTED EXTENSION NOT YET IMPLEMENTED  
**Selection criterion:** `docs/design/state-dependent-harness/extension-choice-criterion.md`

## Section A — Extension statement

**Selected extension:** E1 — source-consuming substitution.

Selection is governed solely by the frozen extension-choice criterion. E1 is selected only after candidate evaluation under P1–P5; the evaluation record must remain immutable and must not use behavioral experiment results.

## Section B — Semantic delta

To be completed before implementation and after the selected extension's exact semantic boundary is frozen.

Required fields:

- State fields added/changed:
- Candidate-generator checks added/changed:
- Substitution signature changes:
- Source-consumption transition:
- Closure changes:
- Activation semantics:
- Files/functions affected:

No implementation has yet been authorized by this document.

## Section C — Prediction

**R:** UNDEFINED — must be constructed and frozen before implementation.

**Trigger_R(S):** UNDEFINED.

**Expected step k:** UNDEFINED.

The prediction MUST have the form:

> `R` activates in `T_A` at step `k <= budget` and does not activate in `T_B` before `budget`.

No alternative outcome is permitted in the preregistered prediction.

## Section D — Negative control

Two executions using the identical traversal choices, in the identical order, from the identical initial state MUST produce identical results.

Formally, if:

`T_1 = T_2`

as an ordered sequence of selected transitions, then:

`Closure(T_1) = Closure(T_2)`

and all recorded state objects and provenance events must agree.

Failure is a harness/implementation defect, not evidence of path dependence.

## Section E — Positive control

**T_A:** UNDEFINED until R and its trigger are frozen.

**T_B:** UNDEFINED until R and its trigger are frozen.

**k\*:** UNDEFINED until paper construction is complete.

The positive control MUST be constructed on paper before implementation. It must identify a state `S*` satisfying `Trigger_R(S*)` on T_A while the corresponding T_B state does not satisfy the trigger by the preregistered budget.

The construction must demonstrate irreversible future-state divergence, not merely a step-count delay.

## Section F — Endpoints and Kill

Primary endpoint:

`K1 := Closure(T_A) != Closure(T_B)`

Secondary endpoint:

`K2 := |Closure(T_A)| != |Closure(T_B)|`

Kill condition:

`KILL := not K1 AND not K2`

A scheduling delay without a closure-set difference is not a positive result.

## Section G — Reuse of B1

B1 is reused without modification:

`C(S) = full shared candidate set`

`K(c) = (canon(source), canon(target), canon(operator))`

`T_A = argmin K(c)`

`T_B = argmax K(c)`

No strategy-specific candidate filtering is permitted.

If implementation of E1 requires modification of B1, this preregistration is invalid and the change constitutes a new extension/design decision.

## Section H — Scope revision

Section 0 remains a valid negative result for the original root-2 operator set.

E1 changes the source-preservation keystone by introducing source consumption. Therefore Section 0 must be treated as:

> **SCOPED TO ORIGINAL OPERATOR SET — NOT INVALIDATED**

It must not be rewritten as an error. The extension changes the assumptions under which the original algebraic result was established.

## Section I — Pre-registration boundary

Before the first implementation/content run, the following MUST be frozen:

1. exact E1 semantic delta;
2. exact State transition for source consumption;
3. exact `R` and `Trigger_R(S)`;
4. exact expected step `k`;
5. paper-constructed positive-control pair;
6. negative-control construction;
7. K1/K2/KILL definitions;
8. B1 reuse without modification;
9. budget and its justification;
10. immutable design hash.

No implementation, simulation, behavioral sweep, or result may be used to fill a missing preregistration value after the first content run begins.
