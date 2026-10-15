# Wildberries Offline Fixture Test-Vector Matrix v0.1

Status: DESIGN-ONLY / FAIL-CLOSED / CONSUMES PR #281 + #282

## Scope

This matrix defines future offline test vectors for the PR #281 Wildberries Content-oriented fixture boundary.

It covers complete supported card, missing `characteristics[]`, malformed `characteristics[]`, and ambiguous characteristic candidates.

The matrix does not implement a parser, call Wildberries, add credentials, or modify CI/runtime.

## Contract boundary

```text
fixture -> extractor -> normalizer -> expected RawObservation
```

Raw source shape remains authoritative at the fixture boundary. Canonical attributes are derived only by deterministic, explicitly evidenced rules.

## Vector schema

Every vector MUST declare: `vector_id`, `fixture_id`, `marketplace`, `profile_id`, `case`, `expected_status`, `expected_attributes`, `expected_provenance`, `source_field_trace`.

`expected_status` is restricted to `OBSERVED` or `UNKNOWN`. `VERIFIED` is prohibited.

## Vector matrix

| Vector | Raw condition | Expected status | Expected result |
|---|---|---|---|
| WB-CHAR-001 | complete card with supported `characteristics[]` | OBSERVED | deterministic semantic attributes |
| WB-CHAR-002 | `characteristics` absent | UNKNOWN | no fabricated characteristics |
| WB-CHAR-003 | `characteristics: null` or unsupported type | UNKNOWN | no extraction |
| WB-CHAR-004 | `characteristics[]` item missing required supported fields | UNKNOWN | affected observation unresolved |
| WB-CHAR-005 | characteristic `value[]` has unsupported value type | UNKNOWN | no coercion by guess |
| WB-CHAR-006 | two candidates ambiguously map to one canonical attribute | UNKNOWN | no winner selection |
| WB-CHAR-007 | conflicting values for one canonical attribute | UNKNOWN | conflict preserved; no synthetic resolution |
| WB-CHAR-008 | unsupported nesting replaces expected boundary | UNKNOWN | no heuristic traversal |

## WB-CHAR-001 — complete card

```json
{
  "nmID": 123456,
  "vendorCode": "EXAMPLE-001",
  "dimensions": {
    "length": 100,
    "width": 850,
    "height": 2000,
    "weightBrutto": 25,
    "isValid": true
  },
  "characteristics": [
    {"id": 1, "name": "Материал", "value": ["сталь"]},
    {"id": 2, "name": "Ширина, мм", "value": ["850"]},
    {"id": 3, "name": "Высота, мм", "value": ["2000"]},
    {"id": 4, "name": "Количество дверей", "value": ["2"]}
  ]
}
```

Expected: `OBSERVED`, with material=`сталь`, width_mm=850, height_mm=2000, doors_count=2 only where the future extractor/normalizer contract explicitly evidences those mappings.

## WB-CHAR-002 — missing characteristics

```json
{"nmID":123456,"vendorCode":"EXAMPLE-001","dimensions":{}}
```

Expected: `UNKNOWN` for characteristic observations. No synthesis from title, vendorCode, dimensions, or historical fixtures.

## WB-CHAR-003 — malformed characteristics container

Examples: `"characteristics": null` or `"characteristics": "Материал=сталь"`.

Expected: `UNKNOWN`. No string parsing or type coercion unless separately specified and tested.

## WB-CHAR-004 — malformed characteristic item

```json
"characteristics": [
  {"id":1,"name":"Материал"},
  {"id":2,"value":["850"]}
]
```

Expected: `UNKNOWN` for affected observations. Missing structure is not repaired from nearby fields.

## WB-CHAR-005 — malformed value type

```json
{"id":1,"name":"Материал","value":{"raw":"сталь"}}
```

Expected: `UNKNOWN`. No implicit object-to-string conversion.

## WB-CHAR-006 — ambiguous semantic candidates

```json
[
  {"id":10,"name":"Ширина","value":["850"]},
  {"id":11,"name":"Ширина упаковки","value":["900"]}
]
```

If the contract cannot deterministically distinguish the requested semantic attribute, expected: `UNKNOWN`. No first-match, positional, or popularity heuristic.

## WB-CHAR-007 — conflicting values

```json
[
  {"id":10,"name":"Материал","value":["сталь"]},
  {"id":11,"name":"Материал","value":["алюминий"]}
]
```

Expected: `UNKNOWN`. Conflict remains visible; no arbitrary winner.

## WB-CHAR-008 — unsupported nesting

```json
{"attributes":{"characteristics":[{"id":1,"name":"Материал","value":["сталь"]}]}}
```

Expected: `UNKNOWN` unless that nesting is explicitly added to a future contract and independently tested.

## Provenance invariant

Each vector MUST retain `source=wildberries`, `profile_id=wildberries_by`, `fixture_id`, `source_locator`, `retrieved_at`, `raw_payload_sha256`, and `evidence_status=OFFLINE_FIXTURE`.

Passing an offline vector does not promote the fixture to live-source `VERIFIED`.

## Compatibility with #268/#269/#282

#268 `characteristics{}` remains a legacy/generic mock shape. #281 `characteristics[]` remains the WB Content-oriented source boundary. #282 explicitly prevents treating them as interchangeable. These vectors therefore do not retrofit #268 fixtures or redefine #269 semantics. Canonical convergence occurs only after deterministic extraction/normalization.

## Non-goals

No runtime parser, HTTP/API calls, scraping, credentials, CI changes, schema expansion, or modification of PR #268/#269/#281/#282.

## Frozen Core

`src/jamp/run.py` remains locked at blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

Expected: `Δ(src/jamp/run.py) = 0`
