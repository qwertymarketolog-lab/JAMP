# Marketplace Adapter → Normalization Integration Contract v0.1.1

## Purpose

Design-only contract defining the boundary between concrete marketplace adapters
and deterministic normalization.

Pipeline:

`raw_payload → adapter extraction → raw_source_value + provenance → deterministic normalization → Claim(OBSERVED|UNKNOWN) → EvidencePolicy`

## Integration invariants

1. Adapters extract source values; they do not normalize into verified evidence.
2. Every extracted value retains the original `raw_source_value`.
3. Adapter provenance metadata is preserved through normalization.
4. Canonical attribute names are limited to:
   - `material`
   - `width_mm`
   - `height_mm`
   - `doors_count`
5. Normalization receives exactly one canonical attribute and its raw value.
6. Successful normalization produces `NORMALIZED` and ClaimStatus `OBSERVED`.
7. Any normalization error produces the corresponding error outcome and ClaimStatus `UNKNOWN`.
8. Normalization MUST NOT produce `VERIFIED`.
9. EvidencePolicy remains the sole OBSERVED → VERIFIED promotion boundary.
10. Missing source attributes remain UNKNOWN; adapters MUST NOT invent defaults.
11. Unsupported units remain UNKNOWN; adapters MUST NOT silently convert units.
12. Adapter normalization must be deterministic and side-effect free.
13. Normalization must not overwrite the original source value.
14. Qualification is downstream and cannot consume raw adapter output as verified evidence.

## Adapter output contract

For each extracted Claim:

- `attribute_name` is canonical.
- `value` is the deterministic normalized value when normalization succeeds.
- `raw_source_value` is the unchanged source value.
- `status` is OBSERVED only after successful normalization, otherwise UNKNOWN.
- `metadata` retains source-specific provenance.

The adapter layer MUST NOT assign VERIFIED.

## Source mapping

| Source | Raw field | Canonical attribute |
|---|---|---|
| Ozon | Материал | material |
| Ozon | Ширина | width_mm |
| Ozon | Высота | height_mm |
| Ozon | Количество дверей | doors_count |
| Wildberries | Материал корпуса | material |
| Wildberries | Ширина предмета | width_mm |
| Wildberries | Высота предмета | height_mm |
| Wildberries | Количество створок | doors_count |
| Yandex Market | Материал | material |
| Yandex Market | Ширина | width_mm |
| Yandex Market | Высота | height_mm |
| Yandex Market | Число дверей | doors_count |

## Error propagation

`adapter missing/invalid source value → normalization outcome → UNKNOWN`

The integration layer MUST preserve the normalization error classification:
`MISSING`, `TYPE_INVALID`, `FORMAT_INVALID`, `UNIT_UNKNOWN`,
`NON_FINITE`, `OUT_OF_RANGE`, or `AMBIGUOUS`.

No fallback/default/inference is permitted.

## Provenance invariant

The resulting Claim must preserve:

- canonical attribute name;
- unchanged raw source value;
- source-specific provenance metadata;
- normalization outcome/error classification.

Normalization is a transformation boundary, not an evidence-verification boundary.

## Deterministic vector compatibility

Every vector from PR #261 MUST be representable at this integration boundary
without changing its expected outcome or status.

For each source adapter, equivalent raw values mapped to the same canonical
attribute MUST obey the same normalization contract.

## Scope exclusions

- no runtime adapter implementation
- no marketplace API calls
- no credentials
- no executed tests
- no `.github/workflows/test.yml` changes
- no `src/jamp/run.py` changes
- no EvidencePolicy implementation
- no qualification implementation

## Repository invariants

Parent PR #261 HEAD: `06044e11a84a1ab452218fdef9eac3aebe096888`.
Frozen Core blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
Required Frozen Core delta: 0.

## Status

DESIGN-ONLY / PRE-IMPLEMENTATION
