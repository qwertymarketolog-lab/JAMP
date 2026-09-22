# EXP-21 Phase 3 Final Report

**Status:** CLOSED / NOT_CONFIRMED  
**Research scope:** Phase 3 comparative evaluator, N=100  
**PR:** #143 (research/exp21-phase3-bounding-proposal)  
**Evaluation run:** 35720070160  
**Evaluated HEAD:** 6c7c0ffee819888948ac617f1abcefa1a5d91a35

## 1. Evidence identity

The Phase 3 runner completed successfully at GitHub Actions run 35720070160, job 106720640660.

The uploaded raw-evidence artifact is:

- Artifact ID: 10691360196
- Artifact name: phase3-raw-evidence-json
- Artifact SHA-256: 42a01792ac192b8fa4352396929cd4c4f507260ce22e9dd2c4e75f2e0c43d4f1
- Artifact creation time: 2026-09-22T11:11:45Z

The evaluator verified:

- target commit equals 6c7c0ffee819888948ac617f1abcefa1a5d91a35;
- canonical Phase-0 source blob equals 5995fc4c73a985585abe99f3eea393ef60c857a9;
- workload spec ID equals EXP-21-PHASE0-G4-CANONICAL-V1;
- canonical definition SHA-256 equals f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92;
- runtime payload SHA-256 is 712ef9848524ab4ebcbfd416854dceb23593f7e9ef40e0f071a0c82d844482ba;
- the definition digest and runtime payload digest are distinct identities.

## 2. Frozen fixture validation

The evaluator loaded the frozen Phase 2 N=100 seed fixture and enforced:

- sample size = 100;
- 100 unique integer start nodes;
- no external seed input accepted.

All fixture/provenance checks completed successfully in the Phase 3 job.

## 3. Comparative result

Observed summaries:

| Metric | Control | Treatment |
|---|---:|---:|
| N | 100 | 100 |
| p50 | 102 | 102 |
| p95 | recorded in raw evidence | recorded in raw evidence |
| max | 20,000 | 20,000 |

Derived values:

- tail reduction = 0.0%;
- median delta = 0.0%;
- median threshold (<=102) = PASS;
- tail threshold (<=10,000) = FAIL;
- evaluator decision = NOT_CONFIRMED.

The evidence therefore does not demonstrate tail compression or a >=50% reduction. The measured median equality is an empirical result for this fixed N=100 fixture; it is not a basis for a broader causal claim.

## 4. Mechanism boundary

Under the evaluated cold-start-per-query treatment model, the bounded candidate did not reduce the observed worst-case inspection count on the frozen fixture.

The experiment does not establish a general performance law beyond this workload and protocol. In particular, no causal claim is made about other workloads or execution models.

## 5. Frozen Core

The Phase 3 workflow independently enforced:

`git diff BASE...HEAD -- src/jamp/`

with zero changed files.

**Frozen Core result: Δ(src/jamp) = 0.**

No production/runtime modification was required by this evaluation.

## 6. Final verdict

**EXP-21 Phase 3: NOT_CONFIRMED.**

The research branch state is archived as a completed negative/non-confirming evaluation. This report records the evidence boundary and preserves the distinction between canonical definition provenance and runtime payload identity.

No synthetic PASS, threshold relaxation, or Frozen Core modification is introduced by this report.
