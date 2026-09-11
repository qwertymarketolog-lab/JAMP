# Extension Choice Criterion

**Date:** 2026-09-11  
**Status:** FROZEN BEFORE CANDIDATE EVALUATION  
**Scope:** State-Dependent Harness after `HARNESS_REJECTED_STRUCTURAL`

## 1. Purpose

This document freezes the rule by which candidate extensions E1/E2/E3 will be evaluated. The criterion is independent of the identities and expected performance of the candidates. No candidate is selected by intuition, implementation convenience, or observed experimental result.

## 2. Primary structural requirement

An extension is eligible only if it can break commutativity of state accumulation:

`exists T1,T2: Closure(T1) != Closure(T2)`

for two valid traversals starting from the same `S0+` and using the same extended operator set.

If this cannot be established on paper, the candidate is rejected without further scoring.

## 3. Lexicographic properties

Eligible candidates are compared in the following fixed lexicographic order. Earlier properties dominate all later properties.

### P1 — Breaks commutativity

Does the extension permit two valid traversal orders from the same `S0+` to produce different closures or permanently different future applicability?

`YES > NO`

`NO` is an immediate rejection.

### P2 — Preserves S0+

Does the initial closure on root=2 remain the existing S0+ state?

`YES > NO`

A `NO` does not necessarily make the extension invalid, but it receives lower rank because it expands the semantic delta to the baseline itself and requires revalidation of prior analyses.

### P3 — Minimality of semantic change

Rank by the number and architectural depth of modified semantic surfaces, in this fixed preference order:

1. existing control-flow invocation only;
2. existing candidate-generation semantics;
3. State representation;
4. rule-activation semantics;
5. multiple simultaneous semantic surfaces.

Fewer/deeper-surfaces wins over more/deeper-surfaces.

### P4 — Preservation of Section 0 keystone

Does the extension preserve `substitution preserves source`?

`PRESERVE > EXPLICITLY REVOKE`

If the extension revokes the keystone, Section 0 remains valid for the original operator set but becomes explicitly scoped to that set. Revocation is not an error; it is a semantic delta that must be recorded.

### P5 — Positive-control testability

Can a concrete pair of traversals and a specific gated rule R be constructed on paper such that novelty and path-dependence are both true before implementation?

`YES > NO`

A candidate without a constructible positive control is rejected.

## 4. Tie-break

If two candidates remain lexicographically equal after P1–P5, the tie-break is:

> Prefer the candidate requiring fewer changed semantic lines/surfaces in `track_a/common.py` and its directly coupled State/candidate code.

If the tie-break still cannot distinguish candidates without inspecting implementation results, selection is declared unresolved and the criterion is incomplete; no vote or intuition is permitted.

## 5. Evaluation boundary

Candidate evaluation is paper/design analysis only. No simulation, dry-run, implementation, benchmark, or observed result may be used to improve a candidate's score before selection.

The selected candidate must be determined solely by P1–P5 and the frozen tie-break.

## 6. Frozen status

This criterion is frozen before evaluation of E1, E2, and E3.

No candidate-specific conclusion is part of this document's frozen rule. Candidate results, once obtained, must be recorded as an appendix or separate evaluation artifact rather than changing the criterion retroactively.
