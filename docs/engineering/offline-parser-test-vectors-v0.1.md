# Offline Parser Test Vector Contract v0.1

Status: DESIGN-ONLY

## Purpose

Define deterministic offline parser vectors for Ozon, Wildberries, and Yandex Market.

Vectors specify expected parser behavior without implementing the parser or performing network/API access.

## Vector boundary

`fixture -> extractor -> normalizer -> expected RawObservation`

Each vector MUST declare:

- `vector_id`
- `fixture_id`
- `marketplace`
- `case`
- `expected_status`
- `expected_attributes`
- `expected_provenance`

## Positive vectors

Each marketplace MUST have a positive vector covering:

- material;
- width_mm;
- height_mm;
- doors_count.

Expected status: `OBSERVED`.

Canonical expectations:

| Marketplace | material | width_mm | height_mm | doors_count |
|---|---|---:|---:|---:|
| Ozon | steel | 850 | 2000 | 2 |
| Wildberries | сталь | 850 | 2000 | 2 |
| Yandex Market | steel | 850 | 2000 | 2 |

## Fail-closed vectors

Each marketplace MUST have vectors for:

1. missing attribute -> `UNKNOWN`;
2. malformed numeric value -> `UNKNOWN`;
3. ambiguous value -> `UNKNOWN`;
4. unsupported unit -> `UNKNOWN`;
5. absent payload field -> `UNKNOWN`.

No vector may expect fabricated values.

## Provenance invariant

For every vector, the expected observation MUST preserve:

- `marketplace`;
- `source_locator`;
- `fixture_id` as test provenance;
- `retrieved_at` as fixture metadata.

Fixture provenance MUST NOT be promoted to live-source verification.

## Status invariant

Allowed parser statuses:

- `OBSERVED`
- `UNKNOWN`

`VERIFIED` MUST NOT appear as an expected parser result.

## Determinism invariant

Given identical fixture bytes, vector definition, extractor contract version, and normalizer contract version, expected output MUST be identical.

Tests MUST compare canonical values, status, and provenance fields; incidental JSON formatting is irrelevant.

## Offline invariant

Vectors MUST be runnable with network access disabled.

The contract introduces no:

- HTTP/API calls;
- SDK calls;
- browser/headless execution;
- credentials;
- runtime implementation;
- CI configuration changes.

## Compatibility

Vectors consume the fixture contract from Offline Marketplace Fixture Contract v0.1 and the existing marketplace adapter/normalization contracts. They do not redefine extraction or normalization semantics.

## Frozen Core

`src/jamp/run.py` MUST remain unchanged.

Frozen Core blob:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Expected:

`Δ(src/jamp/run.py) = 0`
