# Wildberries Offline Fixture Contract v0.1

Status: DESIGN-ONLY / OFFLINE / FAIL-CLOSED

## Purpose

Define the minimum offline fixture contract for the documented Wildberries Content API response boundary:

`cards[] -> nmID / vendorCode / dimensions / characteristics`.

This contract does not claim to be a complete WB OpenAPI schema. The raw OpenAPI `$ref` graph remains INCONCLUSIVE because the official Swagger artifact could not be extracted from the current environment.

The fixture is test data, not live evidence and not a parser implementation.

## Evidence boundary

The fixture MUST preserve provenance separately from the raw response payload.

| Field | Contract |
|---|---|
| `source` | `wildberries` |
| `profile_id` | `wildberries_by` |
| `source_locator` | mandatory exact locator for the captured source |
| `retrieved_at` | mandatory UTC retrieval timestamp |
| `raw_payload_sha256` | mandatory SHA-256 of the exact raw payload |
| `fixture_id` | mandatory stable fixture identifier |
| `evidence_status` | `OFFLINE_FIXTURE` |

Credentials, authorization headers, cookies, tokens, and secrets MUST NOT be stored in fixtures.

## Fixture envelope

A fixture MUST have an envelope equivalent to:

```json
{
  "fixture_id": "wb-by-cards-v0.1-example",
  "provenance": {
    "source": "wildberries",
    "profile_id": "wildberries_by",
    "source_locator": "REQUIRED",
    "retrieved_at": "2026-01-01T00:00:00Z",
    "raw_payload_sha256": "REQUIRED",
    "evidence_status": "OFFLINE_FIXTURE"
  },
  "payload": {
    "cards": []
  }
}
```

The example above is structural only. Values MUST come from a captured, allowed source before a fixture is used as observed evidence.

## Raw payload preservation

The `payload` MUST preserve source field names, nesting, and value types.

The fixture layer MUST NOT:
- rename `nmID` to `product_id`;
- convert `vendorCode` to another identifier;
- convert dimensions to canonical units;
- translate characteristic names or values;
- infer locale or currency;
- synthesize missing fields.

Normalization belongs to the parser/normalizer layer.

## Minimum card boundary

Each observed `cards[]` item may expose:

```text
cards[]
├── nmID
├── vendorCode
├── dimensions
│   ├── length
│   ├── width
│   ├── height
│   ├── weightBrutto
│   └── isValid
└── characteristics[]
    ├── id
    ├── name
    └── value[]
```

This is a minimum fixture boundary, NOT a claim that these are the only properties of a WB card.

## Fail-closed extraction

| Source evidence | Result |
|---|---|
| exact supported field observed | `OBSERVED` |
| field absent | `UNKNOWN` |
| field present with unsupported type | `UNKNOWN` |
| multiple ambiguous candidates | `UNKNOWN` |
| unit cannot be deterministically normalized | `UNKNOWN` |
| language/value mapping cannot be justified | `UNKNOWN` |
| identifier conflict | `UNKNOWN` |
| source nesting differs from supported contract | `UNKNOWN` |

The parser MUST NOT fabricate a value to turn an UNKNOWN into OBSERVED.

## Canonical mapping boundary

The fixture remains raw. A later deterministic normalizer may map:

```text
nmID                 -> product_id
vendorCode           -> source/vendor identifier
dimensions.width     -> width_mm
dimensions.height    -> height_mm
characteristics[]    -> semantic attributes
```

These mappings are implementation requirements to be evidenced by test vectors, not assertions about every future WB payload.

For characteristics, semantic mapping MUST use explicit deterministic rules. Matching by approximate text, transliteration, locale assumption, or guessed position is not sufficient evidence.

## Provenance isolation

The following MUST remain distinct:

```text
raw payload + provenance
        ↓
offline fixture
        ↓
extractor
        ↓
RawObservation
        ↓
canonical normalizer
```

A derived canonical value MUST retain traceability to the source field that produced it.

The fixture MUST NOT be promoted to `VERIFIED` merely because it is syntactically valid or passes deterministic tests.

## Test-vector requirements

Future offline vectors MUST include at least:
1. complete supported card;
2. missing `nmID`;
3. missing `vendorCode`;
4. missing `dimensions`;
5. malformed `dimensions`;
6. missing `characteristics`;
7. malformed/ambiguous characteristic values;
8. conflicting candidate attributes;
9. unsupported unit;
10. unsupported nesting.

Allowed parser boundary statuses:
- `OBSERVED`
- `UNKNOWN`

`VERIFIED` is prohibited at the parser boundary.

## Non-goals

This design does not:
- call Wildberries;
- scrape public pages;
- add credentials;
- implement HTTP transport;
- implement a runtime parser;
- modify CI;
- modify PR #268 or #269;
- claim a complete OpenAPI schema;
- modify the EvidencePolicy or QualificationEngine.

## Frozen Core

`src/jamp/run.py` MUST remain unchanged.

Frozen Core blob:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Expected:

`Δ(src/jamp/run.py) = 0`