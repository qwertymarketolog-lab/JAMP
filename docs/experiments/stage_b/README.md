# JAMP Stage B — Evidence Snapshot

**Status:** PARTIAL_COMPLETED / VERIFIED (snapshot integrity and response classification; model qualification is NOT_STARTED)  
**Experiment:** 3 Models × 3 Tasks (Math Proof, Code Audit, Novelty Proposal)  
**Date:** 2026-11-13

## Provenance & Integrity

- **Source Run ID:** 43411251104
- **Source Git SHA:** 2d7a38cdf2f18ccd8505da14880314923846d256
- **Source Artifact ID:** 14029608135
- **Source Manifest SHA-256:** 840981cbb800d281e823e7295a1e5df851de05017b8f47359b8d715f3d4118a8
- **This Manifest SHA-256:** 8873ecab850c35152e97d2e1c5756417014577786bef024a2f194d1e266aa3f3
- **Artifact Expiry:** GitHub Actions artifact `14029608135` expires approximately 2027-02-11. This repository file preserves the derived classification snapshot after artifact expiry.
- **Regeneration Command:** `python scripts/research/stage_b_benchmark.py --reclassify <path-to-source-manifest.json>`

The derived manifest is committed as a versioned evidence snapshot. It does not replace or modify the original raw response files or source manifest.

## Execution Summary

- **Planned Requests:** 9
- **HTTP-successful requests:** 8
- **Incomplete transport reads:** 1 (Astra Task 2; HTTP status unknown)
- **Total Attempted:** 9

## Response Classification (Strict)

Out of 9 planned requests, the actual content status is:

- **RESPONSE_COMPLETE:** 3 (Astra Task 1, Astra Task 5, Nemotron Task 1)
- **RESPONSE_EMPTY:** 4 (DeepSeek Tasks 1/2/5, Nemotron Task 2)
- **RESPONSE_TRUNCATED:** 1 (Nemotron Task 5)
- **INCOMPLETE_READ:** 1 (Astra Task 2)

**Important limitation:** HTTP 200 does not imply a usable response. All three DeepSeek attempts returned empty content with `finish_reason=length`; provider usage metadata reports 2,038 / 2,048 / 2,048 reasoning tokens respectively. This is an observed association in this run, not proof that reasoning-token consumption caused the empty outputs or that a particular token limit is generally inadequate.

## Financial Reconciliation

- **Calculated debit for requests with usage evidence:** 28,369.5 units
- **Observed provider balance drop:** 28,371 units
- **Difference:** 1.5 units
- **Astra Task 2:** `billing_status=AMBIGUOUS`; estimated charge 624 units; actual charged units remain `null`.

The observed balance drop is consistent with the calculated debit for requests with usage evidence within 1.5 units. Adding the estimated 624-unit Task 2 charge would exceed the observed balance drop by 622.5 units. The provider charge for the incomplete Task 2 request is therefore not established and must not be reported as confirmed.

## Model Qualification

**Status: NOT_STARTED.**

This run records raw responses and a derived completeness classification; it does not qualify any model. Only 3 of 9 attempts contain complete responses. A separate Stage B v2 experiment is needed before model qualification can be attempted.
