# AnyModel Identity & Capability Audit v3 — Contract

**Status:** DESIGN / EXECUTION CONTRACT v3  
**Scope:** all 87 models from the AnyModel catalog  
**Availability prerequisite:** `artifacts/research/anymodel_availability_n3.json`  
**N=3 reuse:** mandatory; this audit MUST NOT repeat the availability probes.

## Contract

Each model receives exactly 30 checks, R01–R30. Every check records only
`VERIFIED | CONTRADICTED | INCONCLUSIVE`, raw observations, and a SHA-256
evidence digest.

| ID | Tier | Frozen assertion |
|---|---|---|
| R01 | P0 | transport request receives an observable response |
| R02 | P0 | elapsed request time is within the configured timeout |
| R03 | P0 | rate-limit response is classified from provider HTTP evidence |
| R04 | P0 | OpenAI-compatible response shape is valid |
| R05 | P0 | requested model ID equals catalog model ID |
| R06 | P0 | declared language assertion is satisfied by deterministic probe |
| R07 | P0 | unexpected-language insertion is absent under the probe boundary |
| R08 | P1 | context-window capability is established by a frozen length ladder |
| R09 | P0 | exact instruction assertion is satisfied |
| R10 | P1 | structured-output capability is established by provider-supported schema evidence |
| R11 | P0 | response is valid under the declared format contract |
| R12 | P1 | tool-calling capability is established by deterministic protocol evidence |
| R13 | P1 | streaming capability is established by streaming transport evidence |
| R14 | P1 | system-instruction handling is established by deterministic probe |
| R15 | P1 | multi-turn state handling is established by deterministic probe |
| R16 | P1 | repeated deterministic probe behavior is recorded without semantic judging |
| R17 | P1 | explicit seed control is verified only when provider evidence exposes it |
| R18 | P0 | claims are extracted using a frozen deterministic extraction contract |
| R19 | P0 | claims are verified only against independently retrieved evidence |
| R20 | P0 | cited references resolve under the retrieval contract |
| R21 | P0 | citation target content satisfies the frozen content-match predicate |
| R22 | P0 | unresolved/inconsistent citation identity is recorded deterministically |
| R23 | P0 | mathematical result agrees with an independent deterministic checker |
| R24 | P0 | returned code satisfies the frozen parse/compile/test contract |
| R25 | P1 | vision capability is verified only with an actual image-input probe |
| R26 | P1 | long-context capability is verified with a frozen token-length ladder |
| R27 | P0 | controlled canary leakage is detected by exact byte/string matching |
| R28 | P2 | reasoning-trace policy is recorded only from observable provider behavior |
| R29 | P2 | safety boundary is tested only with a frozen deterministic policy suite |
| R30 | P0 | provider usage/cost metadata is internally consistent when exposed |

## Evidence rules

- Missing required evidence => `INCONCLUSIVE`.
- No LLM-as-judge.
- No majority vote.
- No inference from catalog metadata that a runtime capability exists.
- A model marked unavailable by the prior N=3 artifact is still represented in
  v3; the artifact is reused as provenance and is not silently converted into
  a v3 capability verdict.
- No status `PASS`, `FAIL`, or `GREEN`.
- The Frozen Core remains untouched.

## Execution identity

The result MUST record:

- exact catalog snapshot;
- exact model ID;
- v3 contract version;
- reused N=3 artifact path and digest when available;
- probe timestamp;
- raw observation;
- evidence digest;
- final per-check status.

The first implementation is deliberately fail-closed for capabilities that
need additional frozen input contracts (for example vision, long-context,
tool calling, citations, and safety). Those checks MUST NOT be upgraded to
VERIFIED merely because an endpoint accepts a request.
