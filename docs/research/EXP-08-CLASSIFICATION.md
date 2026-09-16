# EXP-08 — Classification Layer

**Status:** CLASSIFIED  
**Mutation Score:** PENDING  
**Overall verdict:** PENDING  

## 1. Purpose

This document records the A/B/C/D classification of the 12 raw observations produced by the verified EXP-08 execution.

It is an interpretation layer over the frozen specification and raw execution evidence. It does not modify or replace the raw observations.

## 2. Evidence Chain

- Frozen specification: `docs/research/EXP-08-SPEC.md`
- Raw execution record: `docs/research/EXP-08-EXECUTION.md`
- CI workflow run: `35061282830`
- CI artifact: `exp-08-raw-observations`
- Artifact SHA-256: `eb3a7d23c7c877e1ef9cca8ad82090a4dc426adc641b0fed272b3394a1df349`
- Raw execution commit: `f75250ba0e0c1e28bd12eb6e704f4d4977c4c147`
- Raw execution blob: `fdf9fb47e8234d5bc20c3371c5c512745a6aabde`

The raw execution document contains the scalar observations transcribed from the CI artifact and explicitly applies no A/B/C/D classification.

## 3. Classification Rules

The classifications below apply only the frozen definitions in EXP-08-SPEC §5:

- **A — Observable Difference:** replay succeeds, but one or more observable outputs differ.
- **B — Structural Rejection:** replay rejects the mutation through an expected structural condition.
- **C — Silent Acceptance:** the mutation is accepted without a significant observable difference.
- **D — Unexpected Failure:** the mutation produces an exception or behavior outside the predefined expected surfaces.

A changed DAG hash is not treated as protective detection merely because it differs.

## 4. Classification Matrix

| Mutation | replay | Observable result | Class | Basis |
|---|---|---|---|---|
| M1-CLOCK-A | success | DAG hash differs; merged result remains `Merged=60` | A | Observable output differs |
| M1-CLOCK-B | success | DAG hash differs; merged result remains `Merged=60` | A | Observable output differs |
| M2-REVERSE | success | DAG hash unchanged; merged result remains `Merged=60` | C | No significant observable difference |
| M2-SHUFFLE | success | DAG hash unchanged; merged result remains `Merged=60` | C | No significant observable difference |
| M3-PARENT-REMOVE | success | DAG hash differs; merged result remains `Merged=60` | A | Observable output differs |
| M3-PARENT-INJECT | success | DAG hash differs; merged result remains `Merged=60` | A | Observable output differs |
| M4-WORKER-PAYLOAD | success | DAG hash differs; merged result remains `Merged=60` | A | Observable output differs |
| M4-JOIN-PAYLOAD | success | DAG hash differs; merged result becomes `Merged=61` | A | Observable outputs differ |
| M5-DELETE-WORKER | success | DAG hash differs; merged result remains `Merged=60` | A | Observable output differs |
| M5-DELETE-JOIN | rejected | `ValueError`: exactly one JOIN required | B | Expected structural rejection |
| M6-INJECT-WORKER | success | DAG hash differs; merged result remains `Merged=60` | A | Observable output differs |
| M6-INJECT-JOIN | rejected | `ValueError`: exactly one JOIN required | B | Expected structural rejection |

## 5. Aggregate Classification

- **A — Observable Difference:** 8
- **B — Structural Rejection:** 2
- **C — Silent Acceptance:** 2
- **D — Unexpected Failure:** 0

No D-class observation was recorded.

## 6. Methodological Boundary

This classification does not assign a mutation-specific PASS/FAIL verdict and does not calculate a Mutation Score.

In particular:

- A classification does not imply that the mutation was defensively detected.
- A changed DAG hash is an observable difference, not by itself evidence of protective detection.
- B classifications identify expected structural rejection under the frozen R0 contract.
- C classifications record silent acceptance and do not, by themselves, establish that the accepted mutation is harmless.
- D is reserved for behavior outside the predefined expected surfaces; none was observed.

## 7. Publication State

The classification layer is complete, but the final EXP-08 verdict remains pending application of the mutation-specific rules in EXP-08-SPEC §9.

`docs/research/evidence-index.md` is intentionally unchanged at this stage. No final publication is claimed by this document.

## 8. Next Stage

The next independent step is to inspect and apply the frozen §9 verdict rules to the already-fixed classifications. The A/B/C/D classification itself must not be changed in response to that later evaluation.
