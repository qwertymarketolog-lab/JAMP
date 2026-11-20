# G6 E2E Read-only Investigation Plan

**State:** HOLD  
**Decision date:** 2026-10-12  
**Baseline branch:** `main`  
**Baseline commit:** `d0453eb8ba6c4528dfa84632440404cb6aedeee9`  
**Scope:** Discovery and evidence planning only. This document does not implement an E2E test and does not claim G6 is verified.

## Decision preserved

G6 remains **HOLD** until one terminal, commit-bound E2E execution demonstrates the same request flowing through:

`API Gateway → Capability Router (17-model matrix) → Runtime → Audit Trace → exported/persisted evidence`

The trace identifier must be preserved and correlated across the chain. Passing component tests alone is not sufficient. Missing evidence is not PASS. Do not create a duplicate implementation PR before the read-only inventory establishes that an equivalent test does not already exist.

## Baseline observations

The following are repository observations at the baseline commit, not a claim that every relevant test or workflow has already been exhaustively reviewed:

- `tests/integration/test_offline_vertical_slice.py` contains an offline marketplace-to-decision/audit vertical slice. Its code exercises a different path; by inspection alone it does not establish the target Gateway → Capability Router → Runtime → Audit Trace chain.
- `tests/test_api_gateway_v0.py` covers gateway DTO validation, not the complete target E2E flow.
- `src/jamp/api/app.py`, `src/jamp/runtime/p35.py`, `src/jamp/runtime/provenance.py`, `src/jamp/runtime/persistence.py`, and `src/jamp/audit/exporter.py` are initial trace-lineage inspection targets. Their existence or use of `trace_id` does not by itself prove end-to-end propagation.
- The G1–G5 statuses and run IDs in the prior audit are carried forward as reported claims; this document does not independently re-verify those runs.

## Read-only investigation procedure

1. Re-read the current `main` HEAD before continuing. If it differs from the baseline above, record the new SHA and repeat relevant discovery against that commit.
2. Search existing `tests/`, `src/`, workflow definitions, evidence manifests, and artifacts for integration coverage that connects the target components. Inspect candidate files and call sites, not names alone.
3. Build a coverage map for each candidate: ingress path, router decision and matrix/version, runtime invocation, audit persistence, export path, and trace-ID assertions.
4. Search existing GitHub Actions runs for the candidate test. Record commit SHA, workflow name, run ID, terminal status/conclusion, job IDs/conclusions, and artifact names/URLs. Distinguish PR CI from post-merge CI on `main`.
5. Compare candidate artifact contents or logs to establish a single correlation key (`trace_id`) from ingress through the final persisted/exported audit record. Do not infer continuity from separate component tests or unrelated artifacts.
6. Record results as **OBSERVED → VERIFIED → INFERRED → UNKNOWN**. If a required link or terminal evidence is missing, keep G6 at HOLD and state exactly what remains unknown.
7. Only after this inventory, decide whether an existing test can be extended minimally or a new test is truly required. No implementation, workflow edits, or new test PR is authorized by this discovery step.

## Minimum target scenario (contract to investigate, not yet implemented)

- Submit one deterministic request through the API Gateway.
- Capture the request/trace identity at ingress.
- Verify the Capability Router decision against the intended 17-model capability matrix; record the matrix identity and decision (including REFUSE if fail-closed conditions apply).
- Verify the runtime result for that same request and identity.
- Verify the audit record is persisted and, where the product path exports it, that the exported record contains the same `trace_id`.
- Assert trace-ID equality across all observed stages; fail closed if a stage drops, replaces, or cannot expose the ID.
- Preserve raw logs/results and publish one terminal CI artifact that ties the evidence to the exact tested commit.

## Evidence required to close G6

A G6 VERIFIED decision requires all of the following:

- [ ] Current tested commit SHA is explicit.
- [ ] One E2E test covers Gateway → Router → Runtime → Audit persistence (and export if included in the claimed scope).
- [ ] The same `trace_id` is asserted across the chain.
- [ ] Terminal GitHub Actions Run → Job evidence exists; record IDs and conclusions.
- [ ] The artifact is present, linked to that run, and contains sufficient raw output to verify the assertions.
- [ ] PR CI and post-merge CI on `main` are reported separately.
- [ ] Frozen Core remains unchanged: `src/jamp/run.py` blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`, with `Δ = 0`.

An absent run, empty jobs list, missing artifact, non-terminal run, or artifact without adequate trace-lineage evidence is **UNKNOWN / HOLD**, never PASS.

## Frozen Core and change control

Frozen Core is locked. This task must not modify `src/jamp/run.py` or change its behavior. The baseline blob was observed as `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`; re-check the blob at the current target commit before making any future verification claim.

Do not change application code, tests, workflows, thresholds, or experiment contracts during this read-only phase. Do not open a duplicate PR if an existing implementation already satisfies the target contract.

## Next action

Continue the read-only inventory at the current `main`: inspect existing integration candidates, trace-ID propagation, relevant workflow definitions, and terminal run/job/artifact evidence. Update this record with concrete file paths and evidence references. Keep **G6 = HOLD** until the closure checklist is fully evidenced.
