# AnyModel v3 Consumer Reliability Qualification

## Scope

Read-only qualification of the existing AnyModel v3 raw audit artifact. No audit rerun and no Frozen Core changes.

- Base main SHA: `61faaee05b709febbdf6477c2bc2f372b28a7c2b`
- Raw audit commit: `0b436ca769aa723144bf6b08053978ec6feea2b3`
- Raw artifact: `artifacts/research/anymodel_identity_capability_audit_v3.json`
- Artifact blob SHA: `0b23e605efbe9fb3bc92e767a1de1a196096f3b6`
- Audit ID: `anymodel-identity-capability-v3-20260926T210417Z`
- Catalog count: 87
- Checks per model: 30
- Total checks: 2,610

## Observed result

| Status | Checks | Share |
|---|---:|---:|
| VERIFIED | 711 | 27.2% |
| CONTRADICTED | 211 | 8.1% |
| INCONCLUSIVE | 1,688 | 64.7% |

Per-model observations:

- 87/87 models contain at least one `CONTRADICTED` check.
- 87/87 models contain at least one `INCONCLUSIVE` check.
- 0/87 models have all 30 checks `VERIFIED`.
- R01 availability: 65 VERIFIED / 22 CONTRADICTED.
- R05 identity: 87 VERIFIED / 0 CONTRADICTED / 0 INCONCLUSIVE.
- R27 canary: 55 VERIFIED / 32 CONTRADICTED.

## Qualification

The raw v3 artifact does **not** support a production-ready / fully-qualified model set.

It also does not provide enough evidence to assign every model to a simple "Available / Intermittent / Non-Compliant" class without introducing an additional classification contract.

Therefore this report records the qualification as:

**STATE: INCONCLUSIVE / HOLD**

This is an evidence classification, not a claim that all external-provider failures are caused by JAMP.

## Provenance limitation

Every check in the raw artifact has:

`metadata.execution_id = null`

Therefore the artifact preserves per-check observations and evidence digests, but does not contain a runtime execution identity that can independently bind each observation to a specific audit execution.

The existing Research Loop CI result proves CI processing of the repository state; it is not treated as proof of a direct AnyModel runtime execution.

## Frozen Core

No changes are made to `src/jamp/run.py`.

Frozen Core reference:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

## Decision boundary

This report closes the read-only classification of the existing v3 artifact. It does not synthesize a PASS, create a Trusted Consumer Set, or rerun the 87-model audit.

