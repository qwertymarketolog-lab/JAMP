# Audit Layer B — P18 Subsystem & Cross-Subsystem Verification

- **Audit layer:** B
- **Scope:** P18 subsystem isolation, P17→P18 bridge, deterministic artifact projection, historical verification envelope
- **Audit mode:** forensic / read-only analysis; report-only staging write
- **Main base:** db74be8baeb321dc4c6453c6e3f0f7a80f7b6300
- **PR #111 head before this report:** dee1c3825db07d64187e736e272c9f59cce1ca48
- **Frozen Core:** src/jamp/run.py unchanged; Δ = 0; PATCH = 0

## Executive finding

P18 subsystem code is statically isolated from the Frozen Core and does not show a P17 execution re-evolution path. The P17→P18 bridge is a deterministic pure projection: it constructs an artifact from an existing ExperimentResult and computes local derived artifact metrics, but does not rerun P17 execution, evaluator, trajectory generation, policy adaptation, replay, or causal evolution.

The material unresolved issue is the **verification-envelope disconnect**. The historical P18.4 candidate tree contains the dedicated ablation and adversarial integration tests, and the historical workflow specification explicitly requires them. Those test files are not present in the current main/staging trees examined for PR #111. The historical Actions run 34212659566 cannot currently be retrieved through the available GitHub Actions API surface: jobs/artifacts returned 404 and no workflow run was returned for target SHA 7b717a8dea269bc5c33d9c128634f55c0bad27b0. Therefore live execution of that historical run is not asserted.

## Evidence matrix

| Vector | Status | Evidence |
|---|---|---|
| P18 code isolation | VERIFIED | P18. controlled_transfer.py, experiment_registry.py, task_family_isolation.py contain no imports to src/jamp/run.py or src/jamp/core.py. |
| Task-family fail-closed boundary | VERIFIED | Missing family identifiers, conflicts, and foreign-family transfers are rejected; mappings/object values are isolated by copying. |
| P17→P18 bridge | VERIFIED | Candidate P17 closed_loop.py adds ExperimentResult.to_artifact() as a local projection bridge. |
| Deterministic projection | VERIFIED | from_experiment_result() builds ExperimentArtifact from existing result state and computes local derived metrics; no execution re-evolution occurs. |
| Historical P18.4 workflow specification | PROVEN | import-historical.yml explicitly requires tests/test_p18_4_ablation.py and tests/integration/test_adversarial_e2e.py and runs both full pytest and the P18.4 test. |
| Historical P18.4 test presence in candidate | PROVEN | Candidate tree a65b8af692fe6f5b2569a947f878f52830d43e18 contains both required test paths. |
| Run 34212659566 live execution | UNPROVEN | Current GitHub Actions API retrieval returned 404 for jobs/artifacts; commit workflow-run query for target SHA returned no runs. |
| PR #111 verification envelope | MISSING | The 41-file content-addressed staging overlay contains the promoted P18/runtime files but not the two dedicated P18.4 verification tests. |
| P18.4 milestone state | PENDING VERIFIED CI | Repository milestone/provenance documentation explicitly requires matching-head GitHub Actions evidence before GREEN/VERIFIED. |
| Frozen Core | LOCKED | src/jamp/run.py remains unchanged; no main patch was made by this audit. |

## Phase 3 conclusion

The evidence supports a structural verification of P18 isolation and deterministic projection, but it does **not** support a claim that P18.4 historical runtime verification was executed and retained as accessible CI evidence.

The correct forensic classification is:

**VERIFICATION ENVELOPE DISCONNECT — PROVEN STRUCTURALLY; HISTORICAL RUNTIME EXECUTION UNCONFIRMED.**

This is not classified as a P18→Core leakage defect. It is a provenance/verification-envelope gap between the historical candidate tree and the current forensic staging scope.

## PR #111 disposition

PR #111 remains a draft diagnostic staging PR. Its purpose is CI validation and evidence collection; it is not approved for merge by this audit. The staging overlay is intentionally not expanded with the omitted ablation tests, because doing so would change the scope of the content-addressed historical promotion evidence being audited.

## Audit boundary

No production/runtime code was changed by Layer B. No change to src/jamp/run.py is authorized or indicated by this evidence. No GREEN/VERIFIED claim is made for P18.4 without matching-head CI evidence.

**Layer B status: CLOSED — EVIDENCE COMPLETE / VERIFICATION ENVELOPE DISCONNECT RECORDED.**
