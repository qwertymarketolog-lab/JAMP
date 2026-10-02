# Deterministic Qualification Requirement Test Vector Contract v0.1.1

## Purpose

Design-only test-vector contract for PR #264. Vectors define expected deterministic requirement evaluation without implementing or executing a qualification engine.

## Vector schema

Each vector MUST define:
- `id`
- `requirement`
- `claims`
- `expected_verdict`
- `expected_reason`

`expected_verdict` is limited to `QUALIFIED` or `INCONCLUSIVE`.

## Positive vectors

| ID | Condition | Expected |
|---|---|---|
| Q-N01 | one required matching VERIFIED `material=metal` with `EQUALS metal` | QUALIFIED |
| Q-N02 | required VERIFIED `width_mm=1200`, operator `GREATER_THAN 1000` | QUALIFIED |
| Q-N03 | required VERIFIED `height_mm=800`, operator `LESS_OR_EQUAL 800` | QUALIFIED |
| Q-N04 | required VERIFIED `doors_count=2`, operator `GREATER_OR_EQUAL 2` | QUALIFIED |
| Q-N05 | multiple required matching VERIFIED claims | QUALIFIED |

## Fail-closed vectors

| ID | Condition | Expected |
|---|---|---|
| Q-E01 | empty requirement set | INCONCLUSIVE |
| Q-E02 | required claim missing | INCONCLUSIVE |
| Q-E03 | required claim UNKNOWN | INCONCLUSIVE |
| Q-E04 | required claim OBSERVED | INCONCLUSIVE |
| Q-E05 | required VERIFIED value mismatch | INCONCLUSIVE |
| Q-E06 | incompatible value type | INCONCLUSIVE |
| Q-E07 | unsupported operator | INCONCLUSIVE |
| Q-E08 | unresolved conflicting VERIFIED values | INCONCLUSIVE |
| Q-E09 | ambiguous requirement | INCONCLUSIVE |
| Q-E10 | non-required requirement unsatisfied while all required requirements satisfy | QUALIFIED |

## Boundary vectors

| ID | Condition | Expected |
|---|---|---|
| Q-B01 | VERIFIED claim is present but normalization provenance is absent | INCONCLUSIVE |
| Q-B02 | raw provenance exists but claim is not VERIFIED | INCONCLUSIVE |
| Q-B03 | two identical VERIFIED claims from different sources | QUALIFIED |
| Q-B04 | conflicting VERIFIED claims from different sources | INCONCLUSIVE |
| Q-B05 | qualification input attempts to contain a status promotion instruction | INCONCLUSIVE |

## Invariants

1. No vector may produce a verdict other than QUALIFIED or INCONCLUSIVE.
2. No vector permits qualification to promote OBSERVED or UNKNOWN to VERIFIED.
3. Every QUALIFIED vector has every required criterion satisfied by matching VERIFIED evidence.
4. Every fail-closed vector has a deterministic INCONCLUSIVE reason.
5. Empty requirements never qualify by default.
6. Conflicting VERIFIED values never resolve implicitly.
7. Provenance is auditable but cannot substitute for VERIFIED evidence.
8. Equivalent canonical inputs yield the same verdict.
9. Raw source values are not reinterpreted by qualification.
10. Vector evaluation does not require API/network access.

## Compatibility

- PR #258: adapter status boundary preserved.
- PR #259: concrete adapters cannot emit VERIFIED.
- PR #260: normalization outcomes remain upstream evidence transformations.
- PR #261: normalization vectors remain upstream-compatible.
- PR #262: adapter provenance/error propagation remains intact.
- PR #263: EvidencePolicy remains sole OBSERVED → VERIFIED boundary.
- PR #264: requirement schema/operators and QUALIFIED/INCONCLUSIVE semantics are exercised by vectors.

## Scope exclusions

No runtime implementation, no executed tests, no marketplace API calls, no credentials, no workflow changes, no `src/jamp/run.py` changes.

## Repository invariants

Parent PR #264 HEAD: 6949e285be97ec2b0e37c94ca395c436d8361e95.
Frozen Core blob: 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a.
Required Frozen Core delta: 0.

## Status

DESIGN-ONLY / PRE-IMPLEMENTATION
