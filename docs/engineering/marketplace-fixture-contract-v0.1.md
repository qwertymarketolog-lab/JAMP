# Offline Marketplace Fixture Contract v0.1

Status: DESIGN-ONLY

## Purpose

Define deterministic offline payload fixtures for Ozon, Wildberries, and Yandex Market parser testing.

Fixtures are test inputs, not live-marketplace evidence.

## Fixture boundary

`fixture -> Extractor -> Normalizer -> RawObservation`

The fixture layer MUST NOT perform network access.

Each fixture MUST declare:

- `fixture_id`
- `marketplace`
- `format`
- `source_locator`
- `retrieved_at`
- `payload`

`observed_at` belongs to the observation produced by the parser and MUST NOT be fabricated by the fixture unless explicitly present in the source payload.

## Required marketplaces

At least one representative deterministic fixture is defined for:

- Ozon
- Wildberries
- Yandex Market

Fixture payloads MAY be simplified mock payloads, but their field shapes MUST be explicit and stable.

## Provenance rules

Fixture provenance MUST remain distinguishable from live provenance.

The parser test result MUST identify:

- fixture_id;
- marketplace;
- extractor contract version;
- normalizer contract version;
- expected canonical observations.

A fixture MUST NOT be interpreted as proof that a marketplace endpoint currently exists or is available.

## Deterministic test boundary

Given the same fixture bytes and contract versions:

`output_n = output_1`

The test MUST compare canonical output and status, not incidental formatting.

Expected statuses at parser boundary are restricted to:

- `OBSERVED`
- `UNKNOWN`

`VERIFIED` is prohibited.

## Fail-closed cases

Test vectors MUST cover at least:

1. valid canonical value -> `OBSERVED`;
2. missing attribute -> `UNKNOWN`;
3. malformed value -> `UNKNOWN`;
4. ambiguous value -> `UNKNOWN`;
5. unsupported unit -> `UNKNOWN`;
6. preserved source provenance.

Transport failures are represented separately from product observations and MUST NOT become product claims.

## Offline invariant

Contract tests MUST be executable with network access disabled.

No SDK, HTTP client, browser, or marketplace API credential is required.

## Non-goals

This contract does not implement:

- HTTP transport;
- live marketplace access;
- authentication;
- retry/rate-limit handling;
- production scheduling;
- EvidencePolicy promotion;
- Qualification Engine execution.

## Frozen Core

`src/jamp/run.py` MUST remain unchanged.

Frozen Core blob:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Expected:

`Δ(src/jamp/run.py) = 0`
