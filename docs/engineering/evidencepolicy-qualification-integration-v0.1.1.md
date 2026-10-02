# EvidencePolicy → Deterministic Qualification Integration Contract v0.1.1

## Purpose

Design-only contract defining the boundary from policy-evaluated Claims to deterministic qualification.

Pipeline: RawObservation → Adapter → Normalization → EvidencePolicy → VERIFIED/UNKNOWN → DeterministicQualificationEngine → QUALIFIED/INCONCLUSIVE.

## Integration invariants

1. Adapter and normalization layers may emit only OBSERVED or UNKNOWN.
2. EvidencePolicy is the sole boundary authorized to promote OBSERVED → VERIFIED.
3. EvidencePolicy MUST NOT promote UNKNOWN to VERIFIED.
4. Qualification MUST consume only EvidencePolicy output.
5. A required criterion is satisfied only by a matching VERIFIED Claim.
6. A required criterion with UNKNOWN or non-VERIFIED evidence yields INCONCLUSIVE.
7. Qualification MUST NOT infer, guess, default, or substitute values.
8. Confidence, ranking, metadata, and raw source text are non-decisive unless a separate policy explicitly promotes them to evidence.
9. Qualification MUST NOT promote OBSERVED → VERIFIED.
10. Qualification output is limited to QUALIFIED or INCONCLUSIVE.
11. Missing required evidence fails closed to INCONCLUSIVE.
12. Conflicting evidence without explicit deterministic policy resolution yields INCONCLUSIVE.
13. EvidencePolicy and Qualification remain separate decision boundaries.
14. No API call, network access, or runtime side effect is permitted.

## EvidencePolicy input/output

Input: Claims with OBSERVED or UNKNOWN status, with raw provenance and normalization outcome attached.

Output: VERIFIED only when an explicit policy rule is satisfied; otherwise UNKNOWN remains UNKNOWN. Provenance remains attached.

## Qualification input

The engine receives policy-evaluated Claims, deterministic requirements, and preserved provenance. Required claims that are not VERIFIED are insufficient.

## Deterministic qualification semantics

Required attribute + matching VERIFIED value → criterion satisfied.
Missing / UNKNOWN / non-VERIFIED / unresolved conflict → INCONCLUSIVE.
If all required criteria are satisfied, the engine may return QUALIFIED.

No confidence threshold, heuristic similarity, or source count may replace required VERIFIED evidence unless explicitly defined by EvidencePolicy.

## Provenance invariant

Preserve observation identity, source, source product identifier, raw source value, canonical attribute, normalization outcome, and EvidencePolicy decision/provenance. Qualification may use provenance for auditability but not as an implicit substitute for VERIFIED evidence.

## Fail-closed examples

| Input condition | Result |
|---|---|
| all required claims VERIFIED and matching | QUALIFIED |
| required claim UNKNOWN | INCONCLUSIVE |
| required claim OBSERVED | INCONCLUSIVE |
| required claim VERIFIED but value mismatches | INCONCLUSIVE |
| required claim missing | INCONCLUSIVE |
| unresolved conflicting evidence | INCONCLUSIVE |

## Compatibility

PR #258: EvidencePolicy remains sole OBSERVED → VERIFIED boundary.
PR #259: concrete adapters cannot emit VERIFIED.
PR #260: normalization failures remain UNKNOWN.
PR #261: deterministic vectors preserve OBSERVED/UNKNOWN mapping.
PR #262: adapter→normalization provenance/error boundary is preserved.

## Scope exclusions

No EvidencePolicy implementation, qualification implementation, runtime execution, marketplace API calls, credentials, executed tests, workflow changes, or Frozen Core changes.

## Repository invariants

Parent PR #262 HEAD: e6572497e4dad6ad58fd4d3b94df1bccf49af26a.
Frozen Core blob: 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a.
Required Frozen Core delta: 0.

## Status

DESIGN-ONLY / PRE-IMPLEMENTATION
