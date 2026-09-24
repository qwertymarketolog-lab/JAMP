# ADR: Core Integrity Contract v0

- **Status:** Proposed / design-only
- **Scope:** Frozen Core integrity
- **Contract:** CIC-v0
- **Canonical Core:** `src/jamp/run.py`
- **Canonical Git blob SHA-1:** `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

## Decision

JAMP defines an external Core Integrity Contract (CIC) as a trust boundary around the Frozen Core.

The verifier and canonical manifest live outside `src/jamp/`. They verify the Core read-only and do not depend on executable semantics from the Core.

CIC v0 is deliberately design-only. It introduces no runtime changes to `src/jamp/run.py`.

## Canonical identity

The existing 40-hex value `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` is a **Git blob SHA-1**, not a SHA-256 digest. CIC v0 preserves that already-canonical identity rather than relabeling it. A future manifest may record a second, independently computed SHA-256 digest.

## Protected object

The current Frozen Core is exactly:

```
src/jamp/run.py
Git blob SHA-1: 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a
```

Invariant:

```
observed_core_identity == canonical_core_identity
```

Any mismatch is a hard integrity failure.

## Fail-closed rule

The verifier MUST terminate non-zero when:

- the manifest is missing or malformed;
- a canonical file is missing;
- the observed Git blob identity differs from the manifest;
- an unsupported hash scheme is requested;
- any canonical entry cannot be verified.

A failed integrity check is never converted into PASS, warning-only status, or an inferred equivalent state.

## Mutation policy

The following are prohibited within a CIC-protected change:

- changing the Frozen Core without an explicit Core migration procedure;
- changing the canonical identity to match an observed mutation;
- weakening or bypassing integrity verification;
- treating a merge/synthetic revision as a substitute for the exact intended revision;
- modifying experimental criteria to obtain a passing result.

CIC v0 does not claim that repository files alone can make mutation physically impossible. Repository branch protection, review policy, and CI enforcement remain required operational controls.

## Evidence

A CIC verification record should preserve:

- repository and commit revision;
- manifest revision;
- canonical path;
- expected identity;
- observed identity;
- verification result;
- verifier version.

This evidence is part of the research provenance boundary.

## Separation of concerns

CIC is an integrity contract, not a performance or scientific-result contract.

```
Core Integrity
      ↓
Research Execution Validity
      ↓
Scientific Evidence
      ↓
Decision
```

G4 thresholds, experiment assertions, and scientific criteria remain independent of CIC.

## Non-goals

CIC v0 does not:

- modify `src/jamp/run.py`;
- change JAMP runtime semantics;
- claim OS/kernel-level security;
- replace GitHub branch protection;
- establish practical performance claims for external research.

## Migration rule

A future Core change requires a separate, explicit migration:

```
PROPOSE → REVIEW → NEW CANONICAL IDENTITY → VERIFY → UNLOCK
```

It must not be smuggled into an unrelated feature or experiment.

## v0 boundary

This ADR, the canonical manifest, the external verifier, and the verifier tests form the complete CIC v0 design surface. No other repository changes belong to this PR.
