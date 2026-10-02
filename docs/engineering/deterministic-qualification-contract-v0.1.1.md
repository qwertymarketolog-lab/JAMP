# Deterministic Qualification Contract + Requirement Schema v0.1.1

## Purpose

Design-only contract defining deterministic qualification requirements and the fail-closed qualification boundary after EvidencePolicy evaluation.

## Qualification contract

Input:
- policy-evaluated Claims;
- deterministic requirement definitions;
- preserved provenance.

Output is limited to `QUALIFIED` or `INCONCLUSIVE`.

Qualification MUST consume only Claims whose evidence status has been evaluated by EvidencePolicy. It MUST NOT promote evidence status.

## Requirement schema

Each requirement MUST contain:

- `requirement_id`: stable unique identifier;
- `attribute_name`: one canonical attribute: `material`, `width_mm`, `height_mm`, `doors_count`;
- `operator`: deterministic comparison operator;
- `expected_value`: canonical expected value;
- `required`: boolean, defaulting is forbidden; the field MUST be explicit.

Optional non-decisive field:
- `description`: human-readable explanation only.

No confidence, ranking, source count, heuristic similarity, locale inference, or implicit unit conversion is part of the schema.

## Allowed operators

- `EQUALS`
- `NOT_EQUALS`
- `GREATER_THAN`
- `GREATER_OR_EQUAL`
- `LESS_THAN`
- `LESS_OR_EQUAL`

Operators MUST be applied only to canonical normalized values of compatible types.

## Deterministic evaluation

For each required requirement:

`matching VERIFIED Claim + deterministic operator evaluation → criterion satisfied`

Any of the following yields `INCONCLUSIVE`:

- required claim missing;
- required claim status is `UNKNOWN`;
- required claim status is `OBSERVED`;
- required claim is non-VERIFIED;
- value mismatch;
- incompatible value type;
- unresolved conflict;
- unsupported operator;
- ambiguous requirement.

If every required requirement is satisfied, result is `QUALIFIED`.

An empty requirement set is `INCONCLUSIVE` and MUST NOT qualify by default.

## Multiple claims / conflicts

For a requirement, multiple VERIFIED claims are acceptable only when their canonical values are identical. Conflicting VERIFIED values without an explicit deterministic resolution policy yield `INCONCLUSIVE`.

A VERIFIED claim from one source MUST NOT silently override another VERIFIED claim.

## Evidence boundary

EvidencePolicy remains the sole authority for `OBSERVED → VERIFIED`.
Qualification treats status as an input fact and never upgrades it.

## Provenance

Every evaluated requirement result MUST remain traceable to:
- requirement_id;
- claim/observation identity;
- source and source product identifier;
- raw source value;
- canonical attribute;
- normalization outcome;
- EvidencePolicy decision/provenance.

Provenance is for auditability and MUST NOT substitute for missing VERIFIED evidence.

## Fail-closed examples

| Condition | Result |
|---|---|
| all required requirements satisfied | QUALIFIED |
| required evidence missing | INCONCLUSIVE |
| required evidence UNKNOWN | INCONCLUSIVE |
| required evidence OBSERVED | INCONCLUSIVE |
| verified value mismatch | INCONCLUSIVE |
| incompatible types | INCONCLUSIVE |
| conflicting VERIFIED values | INCONCLUSIVE |
| empty requirements | INCONCLUSIVE |

## Compatibility

- PR #258: EvidencePolicy remains the sole promotion boundary.
- PR #259: adapters emit no VERIFIED evidence.
- PR #260: normalization is deterministic and fail-closed.
- PR #261: vectors define deterministic normalized/error outcomes.
- PR #262: adapter→normalization provenance/error propagation is preserved.
- PR #263: qualification consumes only policy-evaluated Claims and returns QUALIFIED/INCONCLUSIVE.

## Scope exclusions

No runtime implementation, API/network calls, credentials, executed tests, workflow changes, or Frozen Core changes.

## Repository invariants

Parent PR #263 HEAD: e71b572bcf524fbedaee36b24d24ef6c17ae57c2.
Frozen Core blob: 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a.
Required Frozen Core delta: 0.

## Status

DESIGN-ONLY / PRE-IMPLEMENTATION
