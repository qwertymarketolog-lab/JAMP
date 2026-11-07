# AnyModel R18–R24 Frozen Input Contract v0

**Status:** DESIGN-ONLY / PRE-FREEZE  
**Scope:** AnyModel v3 consumer-reliability qualification  
**Contract version:** `r18-r24-frozen-input-v0`  
**Execution:** NONE — this specification does not authorize model execution  
**Frozen Core:** unchanged; `src/jamp/run.py` is out of scope

## 1. Purpose

Define the minimum deterministic input evidence required to evaluate R18–R24 without conflating transport/provenance observations with claim, citation, mathematics, or code evidence.

This contract defines an **input boundary**, not an empirical verdict.

Pipeline:

`MODEL OUTPUT → FROZEN INPUT RECORD → DETERMINISTIC CHECKER → STATUS`

Missing required input remains `INCONCLUSIVE`.

## 2. Common frozen input envelope

Every R18–R24 input record MUST contain:

- `contract_version`: `r18-r24-frozen-input-v0`;
- exact `model_id`;
- exact `probe_id`;
- exact `observed_at`;
- execution/source reference;
- the original model request/input relevant to the check;
- the unmodified model response relevant to the check;
- content-addressed evidence for the supplied input;
- the deterministic checker/extractor version when applicable.

The following MUST NOT be inferred from model IDs, catalog metadata, or prose:

- provider identity;
- task input;
- claims;
- citations;
- retrieved source content;
- mathematical result;
- returned code;
- checker outcome.

## 3. R18 — Claim extraction

Required frozen inputs:

1. exact model response containing the candidate claim;
2. exact task/input;
3. deterministic extraction contract/version;
4. extractor output;
5. evidence digest binding the record.

Existing v3 mapping:

- `model_id` → AVAILABLE;
- `probe_id` / `observed_at` → AVAILABLE;
- v3 `observed` → NOT SUFFICIENT: contains only the fail-closed reason;
- original task/input → NOT AVAILABLE;
- model response → NOT AVAILABLE;
- extractor output → NOT AVAILABLE.

**R18 closure:** NOT POSSIBLE from existing v3 evidence.

## 4. R19 — Claim verification

Required frozen inputs:

1. extracted claim from R18;
2. independently retrieved source/evidence;
3. retrieval timestamp/reference;
4. deterministic verification predicate;
5. binding between claim and source.

Existing v3 mapping:

- model identity/timestamp metadata → AVAILABLE;
- claim → NOT AVAILABLE;
- independent source → NOT AVAILABLE;
- retrieval record → NOT AVAILABLE;
- verification predicate result → NOT AVAILABLE.

**R19 closure:** NOT POSSIBLE from existing v3 evidence.

## 5. R20 — Citation existence

Required frozen inputs:

1. unmodified model response;
2. each cited reference as returned by the model;
3. frozen retrieval contract;
4. retrieval result and status;
5. retrieval timestamp/identity.

Existing v3 mapping:

- `source_ref` → AVAILABLE, but it identifies the v3 transport source;
- model citations → NOT AVAILABLE;
- cited references → NOT AVAILABLE;
- retrieval results → NOT AVAILABLE.

**R20 closure:** NOT POSSIBLE from existing v3 evidence.

## 6. R21 — Citation-content match

Required frozen inputs:

1. citation extracted from the model response;
2. exact retrieved target content;
3. frozen content-match/entailment predicate;
4. deterministic predicate result;
5. binding between citation and retrieved content.

Existing v3 mapping:

- v3 raw metadata → AVAILABLE only as provenance metadata;
- citation target → NOT AVAILABLE;
- retrieved content → NOT AVAILABLE;
- content-match result → NOT AVAILABLE.

**R21 closure:** NOT POSSIBLE from existing v3 evidence.

## 7. R22 — Citation identity

Required frozen inputs:

1. citation string/identifier as returned;
2. resolved target identity;
3. retrieval response;
4. frozen identity-normalization rule;
5. deterministic resolved/unresolved/inconsistent result.

Existing v3 mapping:

- model identity and `source_ref` → AVAILABLE;
- citation identity → NOT AVAILABLE;
- resolved target → NOT AVAILABLE;
- identity comparison result → NOT AVAILABLE.

**R22 closure:** NOT POSSIBLE from existing v3 evidence.

## 8. R23 — Mathematical correctness

Required frozen inputs:

1. exact model mathematical response;
2. exact mathematical task/input;
3. frozen deterministic checker/solver version;
4. checker input;
5. checker output;
6. deterministic comparison predicate.

The model response is data, never the oracle.

Existing v3 mapping:

- model identity/timestamp → AVAILABLE;
- mathematical task → NOT AVAILABLE;
- model mathematical result → NOT AVAILABLE;
- independent checker → NOT AVAILABLE;
- comparison result → NOT AVAILABLE.

**R23 closure:** NOT POSSIBLE from existing v3 evidence.

## 9. R24 — Code correctness

Required frozen inputs:

1. exact code returned by the model;
2. exact coding task/input;
3. frozen parser/compiler/runtime contract;
4. deterministic test fixture;
5. execution output/exit status;
6. binding to the returned code digest.

Existing v3 mapping:

- model identity/timestamp → AVAILABLE;
- returned code → NOT AVAILABLE;
- coding task → NOT AVAILABLE;
- parser/compiler/test fixture → NOT AVAILABLE;
- execution result → NOT AVAILABLE.

**R24 closure:** NOT POSSIBLE from existing v3 evidence.

## 10. Existing v3 field crosswalk

| Field | Existing v3 | Contract use |
|---|---|---|
| `check_id` | YES | identity |
| `model_id` | YES | model binding |
| `probe_id` | YES | provenance |
| `observed_at` | YES | timestamp |
| `source_ref` | YES | execution/source reference |
| `execution_id` | `null` | explicitly unresolved |
| `evidence_digest` | YES | content commitment |
| `observed` | YES | only fail-closed reason for R18–R24 |
| original request/input | NO | required empirical input |
| raw model response | NO | required empirical input |
| claim/citation/math/code payload | NO | required semantic input |
| independent source/checker/test output | NO | required verification input |

These fields establish that the checks were intentionally fail-closed; they do not instantiate the missing R18–R24 evidence contracts.

## 11. Qualification boundary

This contract MUST NOT promote any R18–R24 result to `VERIFIED` merely because:

- the endpoint responded;
- the model identity is known;
- the v3 evidence digest is valid;
- the model appears in the catalog;
- a provenance artifact exists;
- a generic control example exists.

Until the required frozen inputs exist:

`R18–R24 = INCONCLUSIVE`

and the affected candidates remain qualification `HOLD`.

No rerun is implied by this document.

## 12. Freeze rule

This document is a specification of the evidence boundary only. It does not modify the v3 raw artifact, qualification result, audit runner, workflow, thresholds, or Frozen Core.

Any future normative change requires a new contract version.
