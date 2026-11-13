# Stage B v2 — Targeted Completion Results

**Status:** PARTIAL_COMPLETED (6 of 9 planned responses are complete)  
**Experiment:** Targeted continuation of missing Stage B responses with adjusted `max_tokens`.  
**Date:** 2026-11-13

## 1. Provenance

| Field | Value |
|-------|-------|
| Run ID | 43443336439 |
| Job ID | 131946326174 |
| Artifact ID | 14047328339 |
| Artifact SHA-256 | `f662001de8387396191789c2542221810dcbb5d8b16c021308b3c7847c3ba058` |
| Commit SHA | `4dcda23044fe6bc7bbeb0a095c672216685bed4f` |
| Frozen Core blob | `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` |
| Frozen Core Δ | 0 (VERIFIED in the run manifest) |

The artifact contains 7 files: 4 raw responses, catalog snapshot, run manifest, and checksums.  
This RESULTS.md is a derived document; the artifact is the primary evidence.

## 2. Financial Reconciliation

| Field | Value |
|-------|-------|
| Balance before | 20 903 784 balance tokens |
| Balance after | 20 878 429 balance tokens |
| Observed deduction | 25 355 units |
| Calculated deduction | 25 354 units (sum of per-model dashboard details) |
| Discrepancy | 1 unit (reported as rounding) |

**Status: RECONCILED_WITH_1_UNIT_VARIANCE.** The operator-provided balance snapshots and per-request dashboard details indicate that all four Stage B v2 requests were charged, including DeepSeek Task 2. The one-unit difference is retained rather than silently normalized.

This reconciliation concerns the four Stage B v2 requests only. It does not resolve the separate Stage B v1 Astra Task 2 billing status.

## 3. Execution Summary

Four paid requests were sent (not a preflight — see §6).

| Model | Task | Status | Completion tokens |
|-------|------|--------|-------------------|
| Nemotron 3 Ultra | task5 | RESPONSE_COMPLETE | 873 |
| DeepSeek V4 Pro | task1 | RESPONSE_COMPLETE | 5 161 |
| DeepSeek V4 Pro | task2 | RESPONSE_EMPTY | 26 647 |
| DeepSeek V4 Pro | task5 | RESPONSE_COMPLETE | 3 097 |

Cumulative response coverage across Stage B v1 + v2:

| Task | Nemotron | DeepSeek | Astra |
|------|----------|----------|-------|
| task1 (math) | COMPLETE | COMPLETE | COMPLETE |
| task2 (code audit) | EMPTY | EMPTY (API anomaly) | INCOMPLETE_READ |
| task5 (novelty) | COMPLETE | COMPLETE | COMPLETE |

**6 of 9 planned responses are COMPLETE.** Task 2 has no usable complete response for any of the three models; the recorded failure modes differ.

## 4. Task 5 — Comparative Analysis of Three Mechanisms

Each model was asked for one mechanism to reduce code hallucinations without additional API requests. In this sample, all three responses proposed **decoder-level interventions**.

### Nemotron — Latent Type Consistency Constraint (LTCC)

Auxiliary head on hidden state predicts type signatures for the next token; logits are combined with type-head logits weighted by confidence.

- Requires: model modification and joint training on a typed-code corpus.
- Does NOT require: additional API calls or multiple sampling passes.
- Claimed effect: reduces TypeError rate while maintaining Pass@1.
- Self-declared limitations: requires training the auxiliary head; weaker on untyped dynamic code; does not eliminate logical hallucinations.

### DeepSeek — Symbol-Aware Constrained Decoding (SACD)

Pre-extract a symbol table from context; during decoding, mask logits to allow identifiers present in the symbol table, keywords, or builtins.

- Requires: access to logits and ability to modify them before softmax.
- Does NOT require: additional API calls or external parsers/RAG.
- Claimed effect: reduces undefined identifiers; Pass@1 effect is neutral or unknown.
- Self-declared limitations: requires logits access, unavailable in most closed APIs; addresses only undefined-identifier errors, not logic hallucinations.

### GPT-6 Astra — Single-request decoding with compiler filter

Multiple candidate branches within one decoding operation; incremental parser/compiler/type checks per branch; select the best candidate using a combined score (log P plus penalties for syntax/type/test errors).

- Requires: access to beam search or logits.
- Does NOT require: additional API calls.
- Claimed effect: prunes invalid branches during generation and may increase Pass@1.
- Self-declared limitation: for a fully black-box API returning a single text, the mechanism cannot be implemented without API changes or packing candidates into one response.

## 5. Central Finding

**All three responses in this sample proposed mechanisms requiring access to the generation/decoding process.**

The observed pattern is that, when asked to reduce hallucinations without additional API requests, these responses focused on interventions during generation. None of the three Task 5 responses proposed an external verification layer.

**Implication for JAMP:** These particular mechanisms are not directly implementable through JAMP's current closed OpenAI-compatible API interface if it exposes only completed text and no logits, beam-search controls, or intermediate decoding state. This is an interface constraint, not evidence that every possible model-side or external technique is unavailable.

The result supports the architectural motivation for an external Trust Layer: JAMP can verify outputs at the interface boundary even when it cannot control the model's internal decoding. It does **not** establish that an external Trust Layer is the only possible solution or that these three models exhaust the design space.

**Caveat:** This is one experiment with three models answering one prompt. The responses are a small observed sample, not statistically independent proof and not a general theorem about model capabilities. It establishes only that these three responses did not propose an external-verification mechanism.

## 6. Procedural Violations and Anomalies

### 6.1 execute=true dispatched without authorization

The workflow `stage-b-v2.yml` defines `execute: default: false`. At dispatch time the effective value was `true`. The run sent four paid requests without prior authorization in this session.

- **Root cause:** UNKNOWN. The GitHub API evidence available after the run did not expose the original dispatch input value.
- **Attribution:** Not attributed to human error or workflow misconfiguration.
- **Mitigation applied:** None in this run.
- **Recommended mitigation (pending decision):**
  1. Require a literal confirmation value such as `CONFIRM_PAID` for execute=true.
  2. Require a second confirmation step via GitHub Environments.
  3. Split preflight and paid execution into separate workflows.

### 6.2 DeepSeek Task 2 — API anomaly

`max_tokens: 8192` was requested. The provider response recorded:

- `finish_reason: length`
- `completion_tokens: 26 647`
- `reasoning_tokens: 8 192`
- `message.content: null/empty`
- `message.reasoning_content: 101 829 characters`

The reported completion token count exceeds the requested `max_tokens` by more than threefold. The usable content is empty, while the operator-provided balance snapshot and per-request dashboard detail indicate that the request was charged.

**Classification: MODEL_INCOMPATIBLE_WITH_MAX_TOKENS_FORMAT (working label).**

**Not asserted:** that AnyModel or DeepSeek has a bug. The preserved evidence does not independently establish how the provider interpreted the request parameter. The supported observation is that the request produced an empty usable response, reported the token counts above, and incurred a charge.

**Open question:** Is `max_tokens` applied only to content generation while reasoning tokens or other completion accounting follow a separate limit? This remains unresolved and matters for budget policy.

## 7. What This Experiment Does Not Prove

- It does not qualify any model. Qualification requires multiple tasks, multiple seeds, and an appropriate statistical comparison.
- It does not rank the models. The available tasks are not a sufficient benchmark.
- It does not prove the Task 5 mechanisms ineffective; it records their described requirements and limitations.
- It does not prove the Task 5 mechanisms novel. Novelty verification was not performed (`NOVELTY_VERIFICATION=NOT_RUN`).
- It does not establish `MODEL_INCOMPATIBLE_WITH_MAX_TOKENS_FORMAT` as a provider bug. It is a working classification for an observed anomaly.
- It does not prove that an external Trust Layer is the only viable approach or that no model could propose external verification.

## 8. Next Steps

Per the agreed sequence:

1. **Do not run further benchmarks** until `RB-005` (Budget Policy) or `RB-007` (G1 trusted-lineage trigger race) is closed. The experiment cycle has produced data; engineering debt takes priority.
2. **Do not retry DeepSeek Task 2.** The request was charged; the anomaly is documented; retrying without understanding it risks repeating the charge.
3. **Astra Task 2 remains AMBIGUOUS for billing.** The Stage B v1 derived manifest records `astra_task2_billing_status=AMBIGUOUS`, `astra_task2_charged=null`, and `astra_task2_charged_units=null`. The separate Stage B v2 balance reconciliation does not establish whether the Stage B v1 Astra Task 2 charge occurred. The gap remains documented and is not reopened by this experiment's closure.

## 9. Evidence Chain

- Stage B v1 derived manifest: `docs/experiments/stage_b/stage_b_reclassified_manifest.json` (SHA-256: `8873ecab850c35152e97d2e1c5756417014577786bef024a2f194d1e266aa3f3`)
- Stage B v2 artifact: `14047328339` (SHA-256: `f662001de8387396191789c2542221810dcbb5d8b16c021308b3c7847c3ba058`)
- This document is derived from both. The artifacts are primary evidence.
