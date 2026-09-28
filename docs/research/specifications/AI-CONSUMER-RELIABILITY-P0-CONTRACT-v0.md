# JAMP AI Consumer Reliability Audit v0 — P0 Probe Contract

**Status:** DESIGN-ONLY / PRE-FREEZE  
**Layer:** AI Consumer Reliability  
**Version:** p0-probe-v0  
**Matrix:** AI Consumer Reliability Matrix v0  
**Frozen Core:** unchanged; `src/jamp/run.py` is out of scope.

## 1. Purpose

Define the minimum deterministic probe set for the first audit tier. P0 is a cheap funnel stage. It records raw observations and applies deterministic assertions; it does not use another LLM as judge.

Pipeline:

`AI RESPONSE → P0 → P1 (signal) → P2 (deep analysis)`

A P0 result is scoped to the tested assertion. It is not a general model-quality verdict.

## 2. P0 result boundary

Every P0 check produces:

`OBSERVED → STATUS → EVIDENCE`

where:

- `OBSERVED` is the raw machine-readable observation;
- `STATUS` is exactly `VERIFIED | CONTRADICTED | INCONCLUSIVE`;
- `EVIDENCE` is content-addressed by `evidence_digest`.

No P0 implementation may emit `PASS`, `FAIL`, or `GREEN` as the authoritative status.

## 3. Common execution contract

Every probe MUST:

1. use a frozen probe definition;
2. record the exact input/request relevant to the assertion;
3. preserve raw response/status/transport observations;
4. avoid LLM-as-judge evaluation;
5. use deterministic code, parser, checker, retrieval, or provider metadata;
6. fail closed to `INCONCLUSIVE` when required evidence is missing;
7. produce a SHA-256 evidence digest over its canonical evidence record;
8. record `probe_id`, `observed_at`, model/provider identity, and source reference.

A requested property is not evidence that the property occurred.

## 4. P0 checks

| ID | Check | Deterministic assertion | P1/P2 trigger |
|---|---|---|---|
| R01 | Availability | Expected response is received within the configured transport contract | transient/repeated failures |
| R02 | Timeout | Elapsed request time does not exceed the frozen probe timeout; timeout is recorded distinctly | timeout/retry pattern |
| R03 | Rate limit | HTTP/provider response is deterministically classified as rate limiting when provider evidence says so | repeated 429 |
| R04 | Protocol compatibility | Request/response shape matches the declared endpoint protocol | schema/status mismatch |
| R05 | Model identity | Catalog/provider identity matches the requested model identity | alias/version mismatch |
| R06 | Language match | Output satisfies the declared expected-language assertion under the deterministic language detector | mismatch or detector ambiguity |
| R07 | Unexpected language insertion | Unexpected-language spans are detected and measured against the frozen boundary | non-zero/threshold breach |
| R09 | Instruction fidelity | Exact deterministic instruction assertion is satisfied by the raw output | mismatch |
| R11 | Format validity | Raw output parses under the declared format/schema | parse/schema failure |
| R18 | Claim extraction | Claims are extracted by the frozen deterministic extraction contract | extraction ambiguity |
| R19 | Claim verification | Claim has independently retrieved evidence satisfying the frozen verification predicate | missing/contradictory evidence |
| R20 | Citation existence | Each cited reference resolves successfully under the retrieval contract | missing/unresolvable citation |
| R21 | Citation-content match | Retrieved source content satisfies the frozen citation entailment predicate | mismatch/ambiguous entailment |
| R22 | Fabricated citation | Citation target cannot be resolved or is inconsistent with the recorded citation identity | unresolved/suspicious citation |
| R23 | Mathematical correctness | Independent deterministic solver/checker agrees with the claimed result | disagreement or unsupported form |
| R24 | Code correctness | Code parses/compiles/executes against the frozen minimal test contract | execution failure |
| R27 | Secret/canary leakage | Controlled canary is absent from output where absence is required | canary detected |
| R30 | Cost integrity | Provider-reported usage/charge is internally consistent with the recorded request and response metadata | mismatch |

R08, R10, R12–R17, R25–R26, and R28–R29 are not P0 in v0 and require P1/P2 probes.

## 5. Deterministic assertion rules

### R01–R05: transport and identity

- HTTP status, timeout, headers, response shape, catalog identity, and provider metadata are observed directly.
- No semantic interpretation by another model is permitted.
- A transport error is evidence of transport behavior, not proof that the model is nonexistent.

### R06–R07: language

The probe records:

- input language;
- expected language;
- detected language(s);
- language spans;
- unexpected-language ratio;
- detector confidence/version, if applicable.

A language detector ambiguity produces `INCONCLUSIVE`, not a forced classification.

### R09: instruction fidelity

P0 is restricted to exact or parser-checkable assertions, for example:

`Reply with exactly: OK`

Expected raw output:

`OK`

Whitespace/case/normalization rules must be frozen before execution. No semantic judge is allowed.

### R11: format

The expected format/schema is supplied by the probe contract before execution. Parser failure is directly observable.

### R18–R22: claims and citations

P0 may extract structured claims and retrieve references, but it must not infer truth from fluency or confidence.

- extraction is not verification;
- citation existence is not citation correctness;
- citation-content match requires source retrieval evidence;
- unresolved source identity is `INCONCLUSIVE` unless the frozen predicate explicitly defines it as contradiction.

### R23: mathematics

Use an independent deterministic checker. The model output is input data, not the oracle.

### R24: code

Use a sandboxed deterministic parser/compiler/test harness. Execution success is evidence only for the tested code path and test contract.

### R27: canary

Inject a unique non-secret test canary. Detection is deterministic string/byte matching. Real credentials or personal secrets are out of scope for P0.

### R30: cost

Record provider-reported usage and charge fields when available. Missing provider billing evidence yields `INCONCLUSIVE`; zero observed charge must not be interpreted as proof of free service.

## 6. Fail-closed conditions

P0 MUST return `INCONCLUSIVE` when a required observation, parser, provider field, source, or deterministic checker is unavailable.

P0 MUST NOT:

- infer a missing observation;
- substitute another model as judge;
- repair the AI response before checking it;
- convert HTTP failure into model unavailability without protocol evidence;
- convert an empty evidence set into `VERIFIED`;
- use majority vote as an oracle;
- change the Frozen Core;
- alter the assertion threshold after observing results.

## 7. Evidence record

The canonical P0 evidence record is conceptually:

```json
{
  "probe_id": "R07-P0-v0",
  "check_id": "R07",
  "input": {},
  "raw_observation": {},
  "assertion_version": "p0-probe-v0",
  "observed_at": "2026-09-26T00:00:00Z",
  "evidence_digest": "sha256:<64 lowercase hex>"
}
```

The JSON Schema governs the audit result envelope; this contract governs how P0 observations are produced.

## 8. Tier escalation

P0 emits a signal only. Escalation is triggered by a frozen condition such as:

- protocol/transport anomaly;
- language mismatch;
- instruction mismatch;
- parser failure;
- claim/source contradiction;
- mathematical/code checker disagreement;
- canary detection;
- cost inconsistency.

P1/P2 execution must preserve the original P0 evidence and must not overwrite it.

## 9. Provenance boundary

P0 evidence is an observation layer. Classification is derived from the frozen assertion rules. A P0 artifact is not empirical proof of an unrestricted statement about a model.

The contract follows:

`EXECUTION → RAW EVIDENCE → CLASSIFICATION → VERDICT`

and remains subordinate to `PROVENANCE-CONTRACT-v0`.

## 10. Freeze boundary

This document is **DESIGN-ONLY / PRE-FREEZE**. Any normative change after freeze requires a new contract version.

No implementation, workflow, Frozen Core modification, threshold mutation, or empirical model verdict is introduced by this document.
