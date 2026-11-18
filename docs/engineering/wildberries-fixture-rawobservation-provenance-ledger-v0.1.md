# Wildberries Fixture → RawObservation Provenance Ledger Mapping v0.1

Status: DESIGN-ONLY / FAIL-CLOSED / NO-RUNTIME-CHANGE

## Purpose

Define the provenance mapping boundary:

`WB offline fixture -> extractor -> RawObservation -> evidence-ledger entry`.

This document records how identity and source traceability must survive extraction. It does not implement a parser, mutate an existing evidence ledger, or assert compatibility with an uninspected runtime schema.

## Evidence states

| Layer | Allowed meaning |
|---|---|
| offline fixture | `OFFLINE_FIXTURE`; test input, not live verification |
| extracted observation | `OBSERVED` or `UNKNOWN` |
| evidence-ledger entry | records provenance and derivation; does not upgrade source status |
| qualification | downstream decision layer; outside this contract |

`VERIFIED` MUST NOT be emitted by the fixture/parser boundary.

## Identity mapping

The following identities are carried forward without substitution:

| Fixture field | RawObservation / ledger role | Rule |
|---|---|---|
| `source=wildberries` | source identity | preserve exactly |
| `profile_id=wildberries_by` | source profile | preserve exactly |
| `fixture_id` | fixture identity | preserve exactly |
| `source_locator` | source locator | preserve exactly |
| `retrieved_at` | capture timestamp | preserve exactly |
| `raw_payload_sha256` | raw capture identity | preserve exactly |
| `evidence_status=OFFLINE_FIXTURE` | evidence class | preserve; never upgrade automatically |

The mapping MUST NOT replace fixture identity with a generated product identifier.

## Source-field trace

Every derived observation SHOULD retain a deterministic trace:

`RawObservation -> fixture_id -> source_locator -> source_field_path -> raw_payload_sha256`.

For the #281 boundary, examples are:

- `cards[].nmID`
- `cards[].vendorCode`
- `cards[].dimensions.width`
- `cards[].dimensions.height`
- `cards[].characteristics[i].id`
- `cards[].characteristics[i].name`
- `cards[].characteristics[i].value`

A source-field path is descriptive provenance, not permission to infer a canonical semantic mapping.

## Canonical attribute derivation

A future normalizer MAY derive canonical attributes only when an explicit deterministic mapping contract exists.

Example:

`cards[].dimensions.width -> width_mm`

is a mapping requirement to be evidenced, not an assertion that the source unit is always millimetres.

Likewise:

`characteristics[i].name/value -> material | doors_count | ...`

requires an independently specified deterministic rule.

No transliteration, approximate text match, positional guess, locale inference, unit assumption, or first-match selection may create an OBSERVED value.

## Fail-closed ledger rules

| Condition | Observation | Ledger treatment |
|---|---|---|
| exact supported field + deterministic mapping | OBSERVED | record source trace |
| missing field | UNKNOWN | record unresolved field |
| malformed type | UNKNOWN | preserve failure reason |
| ambiguous candidates | UNKNOWN | preserve all relevant candidates/conflict |
| conflicting values | UNKNOWN | preserve conflict; no winner |
| unsupported nesting | UNKNOWN | preserve unsupported path |
| missing provenance | reject vector/fixture | no valid observation |
| offline fixture only | never VERIFIED | retain OFFLINE_FIXTURE provenance |

An UNKNOWN observation MUST NOT be converted to OBSERVED by downstream ledger processing.

## Provenance isolation

The ledger MUST distinguish:

`raw payload identity -> extraction event -> RawObservation -> downstream qualification`.

A derived observation is not the raw payload. A ledger entry is not proof that the source endpoint was live/current. Passing an offline vector is not live-source verification.

## Vector linkage

The #283 vectors MUST map to ledger evidence without changing their expected status:

- `WB-CHAR-001` -> OBSERVED only under explicit deterministic mappings;
- `WB-CHAR-002..008` -> UNKNOWN according to their declared failure condition.

Each linked record retains the vector's `fixture_id` and complete provenance invariant from #281/#283.

## Compatibility constraints

- #268 `characteristics{}` remains a legacy/generic mock shape.
- #281/#283 `characteristics[]` remains the WB Content-oriented fixture boundary.
- #282 remains the compatibility barrier; the two raw shapes are not interchangeable.
- No ledger mapping may silently normalize one raw shape into the other.
- No complete WB OpenAPI schema is claimed; the #281 OpenAPI `$ref` graph remains INCONCLUSIVE.

## Non-goals

No runtime parser, HTTP/API call, scraping, credential handling, CI change, evidence-ledger implementation, qualification change, or modification of #268/#269/#281/#282/#283.

## Frozen Core

`src/jamp/run.py` remains locked at blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

Expected: `Δ(src/jamp/run.py) = 0`.
