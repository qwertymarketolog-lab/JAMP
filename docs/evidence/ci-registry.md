# JAMP — CI Evidence Registry

Status: LIVING DOCUMENT — append-only.  
Scope: verified CI evidence for mandatory and diagnostic workflows.  
Boundary: see [README.md](README.md).

Rule: evidence is tied to an exact revision SHA, workflow, Run ID, and Job ID.  
Artifacts are recorded with their GitHub artifact ID and archive SHA-256 digest when available.  
Historical entries are never rewritten; new evidence is appended.

---

## Main — current verified revision

| Field | Value |
|---|---|
| main SHA | `149badba6bab8a1a1f1f61537462393f6c5ad706` |
| verified at | 2026-10-31 |
| Frozen Core path | `src/jamp/run.py` |
| Frozen Core blob | `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` |
| Δ(Frozen Core) | 0 |

The Frozen Core blob was fetched from `main` and matched the locked blob exactly.

---

## Mandatory post-merge pipelines — VERIFIED

All four runs below are separate mandatory post-merge evidence. They are not included in the diagnostic-workflow coverage count.

### Run Pytest

- Workflow: `.github/workflows/test.yml`
- Run: `41177915375`
- Job: `124469198244`
- Conclusion: SUCCESS
- Revision: `149badba6bab8a1a1f1f61537462393f6c5ad706`
- Evidence: 2176 passed, 1 skipped, 1 deselected, 177 warnings (50.68s)
- Artifact: `13034100220` (`p17-6-experiment-report`)
- Artifact archive SHA-256: `c4d5b0de6885de782cbe336f14ae6789f706f511ede17c03ec6cb5a984dc360d`

### Developer Quality

- Workflow: `.github/workflows/developer-quality.yml`
- Run: `41177915441`
- Job: `124469198555`
- Conclusion: SUCCESS
- Revision: `149badba6bab8a1a1f1f61537462393f6c5ad706`
- Evidence: full suite 2164 passed, 13 skipped, 1 deselected; Phase A 13 passed; EXP-18 R1 6 passed; EXP-18 R2.1 6 passed.
- Baseline: `BASELINE_OK`; base `2dd9ccd16c93978212f0130d957a8d39372e3ade`, head `149badba6bab8a1a1f1f61537462393f6c5ad706`.
- Limitation: changed-Python-file Ruff and Mypy steps both reported `No Python files changed`; neither analyzer actually ran. This run does not establish Mypy coverage for `tests/research/canonical/` or JCS harness files.

### P36.2 G4 MinIO Runtime

- Workflow: `.github/workflows/p36-2-g4-minio-runtime.yml`
- Run: `41177915319`
- Job: `124469197850`
- Conclusion: SUCCESS
- Revision: `149badba6bab8a1a1f1f61537462393f6c5ad706`
- Artifact: `13033828717` (`g4-minio-runtime-evidence`; contains `g4-runtime-evidence.json`)
- Artifact archive SHA-256: `f6c4e3d83f9f0fddabdea2d72449b7dc758832d401465c96bb502a47384f506b`
- Evidence fields in the JSON: `commit_sha=149badba…`, `frozen_core_blob=0fee0e1c…`, `sha256_match=true`, `status=SUCCESS`, `storage_type=minio`, cursor `0 → 70`.

### P23.0-B Cold Replay

- Workflow: `.github/workflows/p23-0-b-diagnostic.yml`
- Run: `41177915304`
- Job: `124469197837`
- Conclusion: SUCCESS
- Revision: `149badba6bab8a1a1f1f61537462393f6c5ad706`
- Evidence: P23 E2E replay 6 passed; structural validation 44 passed; P22.x research gates 120 passed; full suite 2165 passed, 13 skipped.
- Limitation: no artifact was published.

---

## Diagnostic workflows — PR #483 scope (12 files)

PR: #483 — `ci: install dev dependencies in diagnostic workflows`  
Base: `59a0e96052ee216f3d082e46c023dbe89438e10a`  
Merge commit: `149badba6bab8a1a1f1f61537462393f6c5ad706`

### VERIFIED — actually ran, terminal SUCCESS

| Workflow | File | Run | Job | Conclusion | Evidence |
|---|---|---:|---:|---|---|
| P20.5 | `.github/workflows/p20-5-diagnostic.yml` | `41177915416` | `124469198151` | SUCCESS | 32 passed |
| P20.11 | `.github/workflows/p20-11-diagnostic.yml` | `41177915336` | `124469198078` | SUCCESS | 41 passed |

Neither diagnostic run published an artifact.

### CONFIG-ONLY — configuration changed; no actual diagnostic run verified

| Workflow | File | Status | Reason |
|---|---|---|---|
| P19.2 | `.github/workflows/p19-2-diagnostic.yml` | CONFIG-ONLY | no diagnostic run verified |
| P19.3 | `.github/workflows/p19-3-diagnostic.yml` | CONFIG-ONLY | no diagnostic run verified |
| P19.4 | `.github/workflows/p19-4-diagnostic.yml` | CONFIG-ONLY | no diagnostic run verified |
| P20.2 | `.github/workflows/p20-2-diagnostic.yml` | CONFIG-ONLY | no diagnostic run verified |
| P20.3 | `.github/workflows/p20-3-diagnostic.yml` | CONFIG-ONLY | no diagnostic run verified |
| P20.4 | `.github/workflows/p20-4-diagnostic.yml` | CONFIG-ONLY | no diagnostic run verified |
| P22.1 | `.github/workflows/p22-1-diagnostic.yml` | CONFIG-ONLY | no diagnostic run verified |
| P22.2 | `.github/workflows/p22-2-diagnostic.yml` | CONFIG-ONLY | no diagnostic run verified |
| P22.3 | `.github/workflows/p22-3-diagnostic.yml` | CONFIG-ONLY | no diagnostic run verified |
| P22.4 | `.github/workflows/p22-4-diagnostic.yml` | CONFIG-ONLY | no diagnostic run verified |

CONFIG-ONLY does not imply CI-verified. Promotion to VERIFIED requires an actual run with terminal Run → Job evidence; append the new evidence rather than rewriting this historical entry.

Diagnostic coverage at this entry: **2/12 VERIFIED; 10/12 CONFIG-ONLY.** The four mandatory post-merge pipelines above are a separate category.

---

## Known gaps — not proven / not ratified

1. **Mypy coverage**
   - Mypy did not execute in Developer Quality on `149badba` because no Python files changed.
   - Mypy coverage for `tests/research/canonical/` and JCS harness files remains unproven.
2. **N1 freeze** — NOT DONE.
3. **Q1–Q5** — NOT RATIFIED.
4. **Annotation Protocol v0.1 rev.7** — frozen; 12 open questions remain.
5. **Ten of twelve PR #483 diagnostic workflows** — CONFIG-ONLY; see the table above.

---

## Append log

- 2026-10-31: initial registry created. Records the four mandatory post-merge pipelines and the two diagnostic workflows with terminal SUCCESS on main revision `149badba6bab8a1a1f1f61537462393f6c5ad706`. Diagnostic coverage recorded as 2/12 VERIFIED and 10/12 CONFIG-ONLY. Frozen Core Δ=0.
