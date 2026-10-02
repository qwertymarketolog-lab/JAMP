# Marketplace Normalization Deterministic Test Vectors v0.1.1

## Purpose
Design-only test-vector contract for the deterministic normalization layer.
Vectors specify expected outcomes; they do not execute runtime code.

## Vector schema
Each vector defines: `id`, `attribute`, `raw_source_value`,
`expected_normalized_value`, `expected_outcome`, `expected_claim_status`.
For error cases, normalized value is null.

## material — NORMALIZED -> OBSERVED
| ID | Input | Expected | Outcome | Status |
|---|---|---|---|---|
| MAT-N01 | "metal" | "metal" | NORMALIZED | OBSERVED |
| MAT-N02 | "металл" | "metal" | NORMALIZED | OBSERVED |
| MAT-N03 | "  metal  " | "metal" | NORMALIZED | OBSERVED |
| MAT-N04 | "metal  frame" | "metal frame" | NORMALIZED | OBSERVED |
| MAT-N05 | "METAL" | "metal" | NORMALIZED | OBSERVED |
| MAT-N06 | "wood" | "wood" | NORMALIZED | OBSERVED |

## material — error -> UNKNOWN
| ID | Input | Outcome | Status |
|---|---|---|---|
| MAT-E01 | missing | MISSING | UNKNOWN |
| MAT-E02 | null | MISSING | UNKNOWN |
| MAT-E03 | "" | MISSING | UNKNOWN |
| MAT-E04 | 123 | TYPE_INVALID | UNKNOWN |
| MAT-E05 | structurally conflicting representation | AMBIGUOUS | UNKNOWN |

## width_mm / height_mm — NORMALIZED -> OBSERVED
| ID | Input | Expected | Outcome | Status |
|---|---|---|---|---|
| DIM-N01 | 1200 | 1200 | NORMALIZED | OBSERVED |
| DIM-N02 | "1200" | 1200 | NORMALIZED | OBSERVED |
| DIM-N03 | "+1200" | 1200 | NORMALIZED | OBSERVED |

## width_mm / height_mm — error -> UNKNOWN
| ID | Input | Outcome | Status |
|---|---|---|---|
| DIM-E01 | missing | MISSING | UNKNOWN |
| DIM-E02 | null | MISSING | UNKNOWN |
| DIM-E03 | "" | MISSING | UNKNOWN |
| DIM-E04 | 0 | FORMAT_INVALID | UNKNOWN |
| DIM-E05 | -1 | FORMAT_INVALID | UNKNOWN |
| DIM-E06 | "1200.5" | FORMAT_INVALID | UNKNOWN |
| DIM-E07 | "1200 mm" | UNIT_UNKNOWN | UNKNOWN |
| DIM-E08 | "abc" | FORMAT_INVALID | UNKNOWN |
| DIM-E09 | true | TYPE_INVALID | UNKNOWN |
| DIM-E10 | non-finite numeric value | NON_FINITE | UNKNOWN |
| DIM-E11 | outside declared integer range | OUT_OF_RANGE | UNKNOWN |
| DIM-E12 | explicit unsupported unit | UNIT_UNKNOWN | UNKNOWN |

The DIM vectors apply independently to both width_mm and height_mm.

## doors_count — NORMALIZED -> OBSERVED
| ID | Input | Expected | Outcome | Status |
|---|---|---|---|---|
| DOOR-N01 | 1 | 1 | NORMALIZED | OBSERVED |
| DOOR-N02 | "1" | 1 | NORMALIZED | OBSERVED |
| DOOR-N03 | "+2" | 2 | NORMALIZED | OBSERVED |
| DOOR-N04 | 10 | 10 | NORMALIZED | OBSERVED |

## doors_count — error -> UNKNOWN
| ID | Input | Outcome | Status |
|---|---|---|---|
| DOOR-E01 | missing | MISSING | UNKNOWN |
| DOOR-E02 | null | MISSING | UNKNOWN |
| DOOR-E03 | "" | MISSING | UNKNOWN |
| DOOR-E04 | 0 | FORMAT_INVALID | UNKNOWN |
| DOOR-E05 | -1 | FORMAT_INVALID | UNKNOWN |
| DOOR-E06 | "1.5" | FORMAT_INVALID | UNKNOWN |
| DOOR-E07 | "two" | FORMAT_INVALID | UNKNOWN |
| DOOR-E08 | "2 doors" | FORMAT_INVALID | UNKNOWN |
| DOOR-E09 | true | TYPE_INVALID | UNKNOWN |
| DOOR-E10 | non-finite numeric value | NON_FINITE | UNKNOWN |
| DOOR-E11 | outside declared integer range | OUT_OF_RANGE | UNKNOWN |

## Cross-attribute invariants
1. Every NORMALIZED vector maps to OBSERVED.
2. Every error vector maps to UNKNOWN.
3. No vector yields VERIFIED.
4. Raw input remains unchanged in provenance.
5. No inference from another attribute.
6. No implicit unit conversion.
7. Same input/attribute pair always yields same outcome/value.
8. Error classification is deterministic and mutually exclusive.

## Scope exclusions
No runtime implementation, marketplace API calls, credentials, executed tests,
workflow changes, or Frozen Core changes.

## Repository invariants
Parent PR #260 HEAD: `3e7360ce692befa83c25b3ddf61e8d1589d31169`.
Frozen Core blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
Required Frozen Core delta: 0.

## Status
DESIGN-ONLY / PRE-IMPLEMENTATION
