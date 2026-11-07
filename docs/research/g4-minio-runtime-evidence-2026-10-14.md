# G4 MinIO Runtime Evidence — Limited Research Record

**Record date:** 2026-10-14  
**Scope:** P36.2 G4 MinIO runtime / exporter integration  
**Decision:** `PASS` for the tested local-CI runtime contract only  
**Model qualification:** `HOLD / NOT_EVALUATED`  
**Routing:** unchanged; `REFUSE`  
**Frozen Core:** reported invariant `Δ(src/jamp/run.py) = 0`; expected blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

## 1. Observation

The reviewed runtime test exercises a real MinIO/S3 write-and-read path through the storage adapter and exporter. The audit conclusion is that the returned payload is compared byte-for-byte with the original payload and its SHA-256 digest is checked. This supports the integrity of the artifact persisted and retrieved by the tested exporter/storage path; it is not merely a synthetic success flag.

Relevant implementation locations:

- `tests/test_g4_minio_runtime.py`
- `src/jamp/audit/exporter.py`
- `.github/workflows/p36-2-g4-minio-runtime.yml`
- Expected uploaded artifact name: `g4-minio-runtime-evidence`
- Expected artifact file: `artifacts/g4-runtime-evidence.json`

## 2. Evidence boundary

The result establishes only that the tested runtime/exporter/storage path passed in the configured CI environment, within the assertions exercised by the test.

It does **not** establish:

- production MinIO availability, durability, disaster recovery, or operational resilience;
- end-to-end production deployment correctness;
- Gemini 4 Argon capability, answer quality, reliability, or safety;
- that the model generated any particular output correctly;
- model eligibility for execution or a change to product policy.

A successful infrastructure test must not be interpreted as model qualification.

## 3. Frozen Core and product decision

No Task Router or Product Matrix change is part of this record. The audit state remains:

| Area | Recorded status |
|---|---|
| MinIO / exporter runtime contract | `PASS`, limited to tested CI scope |
| Frozen Core | `Δ = 0` as reported by the audit; expected blob recorded above |
| Gemini 4 Argon | `HOLD / NOT_EVALUATED` |
| Routing | unchanged; `REFUSE` |

## 4. Provenance and reuse constraint

This document is a bounded research interpretation, not a replacement for the terminal CI evidence. The exact terminal Run ID, Job ID, artifact ID, and artifact digest are not embedded in this record; they must be resolved from the canonical GitHub Actions Run → Job → artifact chain before this note is used as a fully traceable evidence citation. Do not infer those identifiers from the workflow or artifact name.

If the artifact is absent, non-terminal, or cannot be bound to the exact tested commit, keep the evidence state at `HOLD / INCONCLUSIVE`; do not synthesize a PASS.

## 5. Final classification

**Runtime evidence:** `PASS` — narrowly scoped to the tested CI exporter/storage round-trip and payload-integrity assertions.  
**Model evidence:** none established by this test.  
**Gemini 4 Argon:** `HOLD / NOT_EVALUATED`.  
**Frozen Core / routing:** no intended change.
