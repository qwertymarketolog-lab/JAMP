# Offline Parser Test Vector Compatibility Correction v0.1

Status: DESIGN-ONLY

## Purpose

Correct the offline vector boundary so PR #269 vectors consume the fixture payload
shapes defined by PR #268 and the concrete Ozon/Wildberries/Yandex Market adapter
contracts.

Boundary:

`fixture -> concrete extractor -> deterministic normalizer -> expected RawObservation`

No runtime, API, CI, SDK, browser, or credential changes are introduced.

## Compatibility matrix

| Marketplace | Fixture payload | Concrete extractor | Canonical attributes |
|---|---|---|---|
| Ozon | `payload.attributes[]` | `attributes[].name/values[]` | material, width_mm, height_mm, doors_count |
| Wildberries | `payload.options[]` | `options[].name/value` | material, width_mm, height_mm, doors_count |
| Yandex Market | `payload.parameterValues[]` | `parameterValues[].name/value` | material, width_mm, height_mm, doors_count |

## Positive vectors

| vector_id | fixture_id | marketplace | expected |
|---|---|---|---|
| ozon-positive-v1 | ozon-product-v0.1 | ozon | material=steel; width_mm=850; height_mm=2000; doors_count=2; OBSERVED |
| wb-positive-v1 | wildberries-product-v0.1 | wildberries | material=сталь; width_mm=850; height_mm=2000; doors_count=2; OBSERVED |
| ym-positive-v1 | yandex-market-product-v0.1 | yandex_market | material=steel; width_mm=850; height_mm=2000; doors_count=2; OBSERVED |

## Fail-closed vector contract

For each marketplace, the following vector IDs are normative:

- `<marketplace>-missing-attribute-v1` -> UNKNOWN
- `<marketplace>-malformed-numeric-v1` -> UNKNOWN
- `<marketplace>-ambiguous-value-v1` -> UNKNOWN
- `<marketplace>-unsupported-unit-v1` -> UNKNOWN
- `<marketplace>-absent-payload-field-v1` -> UNKNOWN

These definitions yield 15 fail-closed cases across Ozon/Wildberries/Yandex Market.
No case may fabricate a canonical value.

## Ozon unit boundary

The positive Ozon fixture deliberately uses `"850"` and `"2000"`.

At the current normalization contract:

- digit-only strings -> canonical millimetres and `OBSERVED`;
- `"850 мм"` / `"2000 мм"` -> `UNKNOWN` as `UNIT_UNKNOWN`;
- implicit unit stripping is forbidden.

Therefore the Ozon positive vector does not rely on undocumented unit conversion.

Any future acceptance of explicit `мм` values requires a separate normalization-contract revision and new vectors.

## Provenance invariant

Every vector MUST preserve:

- `marketplace`
- `source_locator`
- `fixture_id`
- `retrieved_at`
- unchanged raw source value
- extractor and normalizer contract versions.

Fixture provenance MUST NOT be promoted to live-source verification.

## Determinism invariant

Identical fixture bytes + vector definition + extractor contract version +
normalizer contract version MUST produce identical canonical values, statuses,
and provenance.

JSON formatting is not part of the comparison.

## Status boundary

Allowed parser outputs:

- `OBSERVED`
- `UNKNOWN`

`VERIFIED` is prohibited.

EvidencePolicy remains the sole `OBSERVED -> VERIFIED` boundary.

## Offline invariant

No HTTP/API, SDK, browser/headless execution, credentials, runtime parser
implementation, or CI configuration is part of this correction.

## Frozen Core

`src/jamp/run.py` MUST remain unchanged.

Locked blob:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Required:

`Δ(src/jamp/run.py) = 0`
