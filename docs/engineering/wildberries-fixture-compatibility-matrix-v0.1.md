# Wildberries Fixture Compatibility Matrix v0.1

Status: DESIGN-ONLY / AUDITED-PR-281 / FAIL-CLOSED

## Scope

This matrix records compatibility between PR #268 (generic offline marketplace fixture contract), PR #269 (offline parser test-vector contract), and PR #281 (Wildberries Content API offline fixture contract).

No runtime implementation is introduced.

## Contract relationship

| Concern | #268 | #269 | #281 | Resolution |
|---|---|---|---|---|
| Fixture provenance | fixture_id, marketplace, format, source_locator, retrieved_at | expected provenance | source, profile_id, source_locator, retrieved_at, raw_payload_sha256, fixture_id | #281 extends provenance for WB BY; no mutation of #268 |
| Raw payload preservation | explicit payload | consumes fixture | explicit source shape/nesting/type preservation | compatible |
| Parser statuses | OBSERVED / UNKNOWN | OBSERVED / UNKNOWN | OBSERVED / UNKNOWN | compatible |
| VERIFIED at parser boundary | prohibited | prohibited | prohibited | invariant |
| Offline/no-network | required | required | required | compatible |
| Canonical normalization | fixture does not normalize | vectors test normalization | normalization remains downstream | compatible |
| Wildberries payload shape | generic mock fixture | canonical expected values | WB Content API-oriented card boundary | shape difference is explicit, not conflated |

## characteristics{} vs characteristics[]

### #268 shape

Existing generic WB fixture:

```json
{
  "characteristics": {
    "Материал": "сталь",
    "Ширина, мм": "850",
    "Высота, мм": "2000",
    "Количество дверей": "2"
  }
}
```

This is a mock fixture shape defined by PR #268.

### #281 shape

WB Content API-oriented boundary:

```text
characteristics[]
├── id
├── name
└── value[]
```

This is the source-oriented fixture boundary adopted by PR #281 from the officially documented Content API response shape available to the project.

### Explicit resolution

The two raw shapes MUST NOT be treated as interchangeable.

```text
#268 mock
characteristics{}
      |
      +-- legacy/generic fixture shape

#281 WB Content boundary
characteristics[]
      |
      +-- source-oriented WB fixture shape
```

A future adapter MAY translate #281 characteristics[] into the canonical semantic representation.
A future compatibility adapter MAY translate the #268 mock shape into the same canonical representation for legacy offline tests.

Neither translation may be inferred bidirectionally from field names alone.

The project MUST NOT rewrite #268 fixtures silently, claim #268's map shape is an actual WB API response, claim every WB payload has the #281 array shape without source evidence, or merge the two raw shapes into one ambiguous fixture schema.

## Compatibility rule

The canonical semantic layer is the only permitted convergence point:

```text
#268 raw mock ------------------+
                                |
                                +-> deterministic extractor/normalizer
#281 raw WB-oriented payload ---+
                                      |
                                      v
                               RawObservation
                                      |
                                      v
                             canonical attributes
```

Raw payload identity and provenance remain separate for each source.

## Fail-closed matrix

| Condition | #268 fixture | #269 vector | #281 contract | Result |
|---|---|---|---|---|
| expected field observed | OBSERVED candidate | OBSERVED | OBSERVED | allowed |
| field absent | allowed fixture | UNKNOWN vector | UNKNOWN | fail-closed |
| malformed value | fixture-dependent | UNKNOWN | UNKNOWN | fail-closed |
| ambiguous mapping | not normalized | UNKNOWN | UNKNOWN | fail-closed |
| unsupported unit | raw only | UNKNOWN | UNKNOWN | fail-closed |
| unsupported nesting | raw fixture shape | UNKNOWN | UNKNOWN | fail-closed |
| conflicting identifiers | no synthetic resolution | UNKNOWN | UNKNOWN | fail-closed |
| provenance missing | contract violation | vector invalid | contract violation | reject fixture/vector |
| VERIFIED parser result | prohibited | prohibited | prohibited | reject |

## Provenance isolation

Fixture identity, source identity, capture identity, derived observation, and downstream qualification evidence MUST remain distinct.

Passing a deterministic offline test does not promote fixture data to live-source verification.

## PR #281 audit disposition

PR #281 is recorded as: AUDITED / DESIGN-COMPATIBLE / NO RUNTIME CHANGE.

Migration consideration: #281 requires raw_payload_sha256; existing #268 fixtures do not currently contain this field. This is an explicit contract extension, not a contradiction. A future migration must be deliberate and must not silently mutate existing provenance.

## Non-goals

This matrix does not modify runtime, PR #268, or PR #269; resolve the unavailable raw OpenAPI $ref graph; introduce WB credentials; perform HTTP/API calls; or establish live WB BY observations.

## Frozen Core

`src/jamp/run.py` remains protected.

Locked blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Expected: `Δ(src/jamp/run.py) = 0`