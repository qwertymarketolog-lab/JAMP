# Wildberries Ledger Test-Vector Matrix v0.1

Status: DESIGN-ONLY / FAIL-CLOSED / PROVENANCE-PRESERVING

## Purpose

Define offline test vectors for the ledger boundary:

`fixture -> extractor -> RawObservation -> evidence-ledger entry`.

The vectors verify that `OBSERVED` and `UNKNOWN` states preserve provenance without synthetic upgrades.

## Required provenance invariant

Every accepted vector record carries:

- `source=wildberries`
- `profile_id=wildberries_by`
- `fixture_id`
- `source_locator`
- `retrieved_at`
- `raw_payload_sha256`
- `evidence_status=OFFLINE_FIXTURE`

The ledger MUST preserve these values exactly.

## Vector schema

Each vector contains:

`vector_id, fixture_id, input_status, expected_status, expected_provenance, expected_trace, case`.

`expected_status` is restricted to `OBSERVED` or `UNKNOWN`.

`VERIFIED` is prohibited.

## Matrix

| Vector | Case | Input status | Expected status | Provenance rule |
|---|---|---|---|---|
| `WB-LEDGER-001` | complete deterministic mapping | OBSERVED | OBSERVED | all provenance fields preserved |
| `WB-LEDGER-002` | missing characteristic | UNKNOWN | UNKNOWN | provenance preserved; unresolved field retained |
| `WB-LEDGER-003` | malformed characteristic container | UNKNOWN | UNKNOWN | provenance preserved; failure path retained |
| `WB-LEDGER-004` | ambiguous candidates | UNKNOWN | UNKNOWN | provenance preserved; ambiguity retained |
| `WB-LEDGER-005` | conflicting values | UNKNOWN | UNKNOWN | provenance preserved; conflict retained |
| `WB-LEDGER-006` | unsupported nesting | UNKNOWN | UNKNOWN | provenance preserved; unsupported path retained |
| `WB-LEDGER-007` | missing provenance field | invalid | REJECTED | no RawObservation/ledger record accepted |
| `WB-LEDGER-008` | offline fixture presented as live evidence | OFFLINE_FIXTURE | OFFLINE_FIXTURE | no VERIFIED upgrade |

## OBSERVED vector

`WB-LEDGER-001` uses the #283 complete card.

Expected:

- canonical observation may be emitted only under an independently evidenced deterministic mapping;
- source-field trace points to exact source paths;
- all provenance fields remain unchanged;
- evidence class remains `OFFLINE_FIXTURE`.

Passing the vector does not establish live WB availability, API schema completeness, or semantic universality.

## UNKNOWN vectors

For `WB-LEDGER-002..006`:

- the failure reason remains visible;
- relevant source-field paths remain traceable;
- provenance is not discarded because extraction failed;
- UNKNOWN cannot be repaired or upgraded by ledger processing;
- ambiguous/conflicting candidates are not collapsed to a winner.

## Provenance rejection

`WB-LEDGER-007` is a provenance-integrity gate.

If any mandatory provenance identity is absent, the fixture is not a valid ledger input. The contract MUST NOT synthesize a missing value from filename, URL fragments, timestamps generated at processing time, product identifiers, or other context.

## Offline/live isolation

`WB-LEDGER-008` verifies that `OFFLINE_FIXTURE` remains an evidence-class marker. Ledger processing MUST NOT infer live/current source status from fixture syntax, successful parsing, or passing tests.

## Trace invariant

For every accepted vector:

`RawObservation -> fixture_id -> source_locator -> source_field_path -> raw_payload_sha256`.

For UNKNOWN vectors, the trace identifies the observed failure boundary rather than inventing a canonical value.

## Compatibility

- Consumes #284 provenance mapping.
- Consumes #283 vector semantics.
- Preserves #282 distinction between `characteristics{}` and `characteristics[]`.
- Preserves #281 provenance requirements.
- Does not modify #268/#269/#281/#282/#283/#284.
- Does not define a complete WB OpenAPI schema.

## Non-goals

No runtime parser, HTTP/API call, scraping, credentials, CI, evidence-ledger implementation, qualification logic, or schema expansion.

## Frozen Core

`src/jamp/run.py` remains locked at blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

Expected: `Δ(src/jamp/run.py) = 0`.
