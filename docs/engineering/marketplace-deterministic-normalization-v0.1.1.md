# Marketplace Deterministic Normalization v0.1.1 — Design Contract

## Purpose

This design-only contract defines deterministic normalization and error semantics
for the concrete marketplace adapter attributes:

- `material`
- `width_mm`
- `height_mm`
- `doors_count`

It is layered on `MarketplaceSourceAdapter v0.1.1` and the concrete Ozon,
Wildberries, and Yandex Market contracts.

No network/API calls, runtime implementation, credentials, tests, CI workflow
changes, or Frozen Core changes are authorized.

## Boundary

```text
raw_source_value
      |
      v
deterministic normalization
      |
      +--> normalized value + OBSERVED
      |
      +--> normalization error -> UNKNOWN
      |
      v
EvidencePolicy
      |
      v
VERIFIED / UNKNOWN
```

Normalization is transformation, not evidence verification.

## Common rules

1. The source-side value MUST be retained unchanged in `raw_source_value`.
2. Normalization MUST be deterministic and side-effect free.
3. No heuristic, confidence score, locale guess, or missing-value default is allowed.
4. A normalization failure MUST produce `UNKNOWN`, never a guessed value.
5. A missing, null, empty, or structurally invalid source value is `UNKNOWN`.
6. Normalization MUST NOT call `EvidencePolicy` or qualification.
7. A successfully normalized value remains `OBSERVED`.
8. Unknown source units MUST NOT be silently converted.
9. Overflow, non-finite numeric values, and ambiguous representations are `UNKNOWN`.
10. The original raw payload remains the immutable observation snapshot.

## material

### Accepted transformation

Input is converted to a deterministic canonical string:

1. Unicode whitespace is trimmed at both ends.
2. Internal runs of Unicode whitespace are collapsed to one ASCII space.
3. Matching is case-insensitive.
4. A finite explicit synonym table MAY map known source spellings to canonical
   values.

The initial canonical mapping is:

| Source value | Canonical value |
|---|---|
| `металл` | `metal` |
| `metal` | `metal` |

No open-ended translation or semantic inference is permitted.

### Error semantics

- null / missing / empty-after-trim -> `UNKNOWN`
- non-string value -> `UNKNOWN`
- unmapped non-empty string -> normalized deterministic string remains
  `OBSERVED`; it is not promoted to a known ontology value
- conflicting or structurally ambiguous source representation -> `UNKNOWN`

The normalization contract therefore distinguishes **canonicalization** from
**ontology verification**.

## width_mm and height_mm

### Canonical type

The normalized value MUST be a positive integer number of millimetres.

Accepted representations:

- integer value `n`, where `n > 0`
- decimal string containing only an optional leading `+` and ASCII digits,
  e.g. `"1200"`

No unit conversion is performed by this contract.

### Rejected representations

The following produce `UNKNOWN`:

- null / missing / empty
- zero or negative values
- fractional values such as `"1200.5"`
- values containing units such as `"1200 mm"`
- non-numeric strings
- booleans
- non-finite numeric values
- values outside the implementation's declared integer range

A source payload that provides a different explicit unit MUST remain
`UNKNOWN` unless a later contract explicitly defines that unit conversion.

## doors_count

### Canonical type

The normalized value MUST be a positive integer count.

Accepted representations:

- integer value `n`, where `n > 0`
- decimal string containing only an optional leading `+` and ASCII digits

### Rejected representations

The following produce `UNKNOWN`:

- null / missing / empty
- zero or negative values
- fractional values
- values containing words or units
- non-numeric strings
- booleans
- non-finite numeric values
- values outside the implementation's declared integer range

No inference from related attributes is permitted.

## Error taxonomy

A runtime implementation MUST expose normalization outcomes equivalent to:

| Outcome | Meaning | Claim status |
|---|---|---|
| `NORMALIZED` | deterministic transformation succeeded | `OBSERVED` |
| `MISSING` | source value absent/null/empty | `UNKNOWN` |
| `TYPE_INVALID` | source value has unsupported type | `UNKNOWN` |
| `FORMAT_INVALID` | value violates canonical grammar | `UNKNOWN` |
| `UNIT_UNKNOWN` | explicit unit cannot be deterministically interpreted | `UNKNOWN` |
| `NON_FINITE` | numeric value is non-finite | `UNKNOWN` |
| `OUT_OF_RANGE` | value exceeds declared implementation range | `UNKNOWN` |
| `AMBIGUOUS` | source representation has multiple plausible interpretations | `UNKNOWN` |

No error outcome may be converted to `VERIFIED` by the normalizer.

## Adapter integration invariant

For every concrete adapter:

```text
raw_source_value
    -> normalize(attribute)
    -> {normalized value, outcome}
    -> ClaimStatus.OBSERVED if NORMALIZED
    -> ClaimStatus.UNKNOWN otherwise
```

The adapter remains prohibited from emitting `VERIFIED`.

`EvidencePolicy` remains the sole `OBSERVED -> VERIFIED` boundary.

## Provenance invariant

Every normalized claim MUST retain:

- source-specific raw value in `raw_source_value`
- source-specific provenance metadata
- canonical attribute name
- normalization outcome/error classification

Normalization MUST NOT overwrite the source-side evidence.

## Scope exclusions

- no Ozon API calls
- no Wildberries API calls
- no Yandex Market API calls
- no credentials or secrets
- no runtime normalization implementation
- no tests or fixtures
- no `.github/workflows/test.yml` changes
- no `src/jamp/run.py` changes
- no EvidencePolicy implementation
- no qualification implementation

## Repository invariants

- Concrete adapter parent: PR #259 HEAD `c9af6f7039b8dcb87cce510e73da396540242ef4`
- Frozen Core: `src/jamp/run.py`
- Locked blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Required Frozen Core delta: `0`
- test workflow delta: `0`

## Status

`DESIGN-ONLY / PRE-IMPLEMENTATION`

Runtime normalization, tests, and terminal evidence require a separate change.
