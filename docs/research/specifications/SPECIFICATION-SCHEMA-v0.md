# Specification Schema v0

**Status:** Draft / Pre-Freeze  
**Layer:** N1 — Specification  
**Governing contract:** `PROVENANCE-CONTRACT-v0`

## 1. Purpose

This document defines the Draft schema for the N1 Specification object in the Normative Research Layer v0.

The Specification is the root pointer and protocol-metadata container for a research execution. It does not contain classification predicates or aggregation rules; those responsibilities belong to Criterion and Criterion Set respectively.

This schema is subordinate to `PROVENANCE-CONTRACT-v0` and must not be interpreted as modifying that frozen contract.

## 2. Schema

```text
Specification:
  spec_id: UUIDv4 / Content-Namespace ID
  spec_version: String (semantic version)
  scope: ScopeDefinition
  hypothesis_ref: HashLink
  prediction_ref: HashLink
  criterion_set_ref: HashLink
  preconditions: List[ConditionRule]
  observation_schema: SchemaDefinition
  evidence_classes: NonEmptyList[EvidenceClass]
  frozen_at: ISO8601 Timestamp | null (Draft only)
  spec_hash: SHA-256
```

### EvidenceClass v0

The Stage B evidence-class vocabulary for `example-001` is:

- `raw_webhook_payload`
- `jamp_runtime_log`
- `provider_request_export`
- `provider_response_export`
- `telegram_send_result`
- `execution_timing_export`

These are evidence-type declarations, not evidence records, hashes, or verdicts. Stage C Raw Evidence v0 is responsible for binding concrete source bytes/records and their `source_sha256` values.

## 3. Field Semantics

### `spec_id`

Immutable identity of the Specification object or its content namespace.

### `spec_version`

Version of the Specification schema/object. A frozen change creates a new version rather than modifying the existing frozen object.

### `scope`

A separately represented, frozen boundary for the research/conformance question. It identifies the domain, system boundary, unit of evaluation, and explicit exclusions. It MUST NOT contain observed results or verdict logic.

For `example-001`, the unit is one execution of:

`Telegram webhook → JAMP Runtime → OpenRouter → Telegram response`.

This is one-run conformance only. It is not an SLA, latency, throughput, availability, reliability, or performance claim.

### `hypothesis_ref`

Content-addressed reference to one exact immutable Hypothesis object. The reference value is expected to bind to the exact `hypothesis_hash` emitted by the Hypothesis record.

### `prediction_ref`

Content-addressed reference to one exact immutable Prediction object. The reference value is expected to bind to the exact `prediction_hash` emitted by the Prediction record.

### `criterion_set_ref`

Content-addressed reference to one exact immutable Criterion Set. The reference must identify the concrete immutable object; symbolic references such as `latest`, `current`, `main`, or equivalent aliases are prohibited.

### `preconditions`

Frozen protocol/state constraints applicable to the execution. They are data/conditions, not classification predicates. For external dependencies, preconditions identify the expected provider/service and requested model without embedding credentials.

### `observation_schema`

Frozen definition of the permitted raw-observation structure. For `example-001`, it must make observable, at minimum:

- the complete incoming Telegram webhook payload as received, including `update_id` and the applicable incoming `message_id`;
- the OpenRouter provider, exact requested model identifier, and the model/version identifier actually reported in the provider response;
- the exact provider request as sent and response as received, including relevant response headers/metadata and a content hash/snapshot reference;
- the Telegram send result, including HTTP/API status and the returned outgoing Telegram `message_id`;
- UTC start/end and key-step timestamps, each with an explicit clock/source designation.

These are observation-shape requirements. They do not assert that the historical E2E run already captured all fields.

### `evidence_classes`

A non-empty list declaring the evidence classes required by the protocol. For `example-001`, the list MUST contain all six EvidenceClass v0 values above. This field declares required evidence types only; it does not claim that any evidence has been collected.

### `frozen_at`

`null` is permitted while the object remains Draft. When the Specification is frozen, this field must contain the concrete freeze timestamp required by `PROVENANCE-CONTRACT-v0`.

### `spec_hash`

SHA-256 computed from the canonical representation of all Specification fields except `spec_hash` itself. Any modification to a covered field produces a different content hash.

The repository's current `canonical.py` is deterministic JSON serialization, but RFC 8785 JCS conformance has not been established. The hash/canonicalization decision remains pre-freeze; this document does not declare the current serializer JCS-compliant.

## 4. N1 Invariants

- **I1:** Specification contains no `acceptance_predicate`, `rejection_predicate`, or `inconclusive_predicate`.
- **I2:** Specification contains no aggregation rule or inline aggregation logic.
- **I3:** `hypothesis_ref`, `prediction_ref`, and `criterion_set_ref` resolve to exact immutable content-addressed objects.
- **I4:** Symbolic or moving references such as `latest`, `current`, or `main` are invalid.
- **I5:** `spec_hash` is deterministic and computed from a canonical representation excluding `spec_hash` itself.
- **I6:** A modification to a frozen Specification requires a new Specification version and immutable identity/hash.
- **I7:** `frozen_at = null` is permitted only before freezing; a frozen Specification must contain a concrete timestamp.
- **I8:** Specification fields must not contain verdict-bearing interpretation introduced after execution begins.
- **I9:** `scope` is a separate field and remains frozen with the Specification.
- **I10:** `evidence_classes` declares required evidence types; it is not a substitute for concrete Raw Evidence.
- **I11:** For `example-001`, all six required evidence classes must be present before one-run conformance can be evaluated.

## 5. Conformance

The schema preserves the frozen `PROVENANCE-CONTRACT-v0` requirements for Specification: identity, version, hypothesis/prediction/criterion-set references, freeze timestamp, and content hash.

The additional `scope` and `evidence_classes` fields are Stage B extensions accepted by the project owner. They do not modify the frozen provenance contract.

The schema does not define Criterion predicates, Criterion Set aggregation, Classification, or Verdict semantics; those remain separate normative objects.

## 6. Freeze Status

This document is **DRAFT / PRE-FREEZE**.

Freeze is blocked until:
1. A2 verification establishes that Hypothesis and Prediction records and their references are compatible with the N1 contract and are actually resolved by the applicable gate.
2. JCS V1–V10 are executed and independently checked, or the serialization contract is explicitly retained as non-JCS with a versioned decision.
3. The `example-001` evidence requirements are backed by a complete real execution; until then the example remains schema-only.
4. The open Q1–Q5 proposals are resolved by explicit owner decisions or kept outside the frozen contract.

No runtime implementation is authorized by this schema package.


## Addendum — 2026-10-31 — Q1–Q5 RATIFIED

Ratified at main `4e7909ef`. Owner decisions recorded.

### Q1–Q5 final

| # | Decision |
|---|---|
| Q1 | JSON Schema — единственный источник истины. YAML не вводится. |
| Q2 | 1 Specification = 1 атомарный research case. Композиция — immutable references. |
| Q3 | Замораживаются 11 нормативных полей: `spec_id, spec_version, hypothesis_ref, prediction_ref, criterion_set_ref, preconditions, scope, evidence_classes, observation_schema, frozen_at, spec_hash`. Post-hoc метрики не замораживаются. |
| Q4 | `spec_hash = SHA-256(canonical_json)`, canonicalization — JCS RFC 8785. |
| Q5 | Criterion — отдельный hash-addressed объект; агрегация — Criterion Set. |

### Superseding

Упоминания `Q1–Q5 PROPOSED` в этом документе superseded ratification от
2026-10-31. Финальные решения — см. эту таблицу. Исторические утверждения
сохраняются как есть.

### Условия N1 freeze — уточнение

Прежний текст требовал полный example-001 evidence run как условие N1 freeze.
Уточняется:

- N1 freeze требует: Q1–Q5 ratified + A2 evidence + Frozen Core Δ=0 +
  `protocol_manifest_sha256` записан со статусом в manifest.
- **Полный example-001 evidence run — НЕ условие N1 freeze.** Это Stage C gate.

Обоснование: связка «N1 freeze ↔ полный example-001» создаёт цикл (схема
не может быть заморожена до прогона; прогон требует замороженной схемы).
Stage B и Stage C — разные gate.

### Что не меняется

- PASS/FAIL критерии не затрагиваются.
- Изменения runtime, тестов, `canonical.py`, Frozen Core — не входят.
