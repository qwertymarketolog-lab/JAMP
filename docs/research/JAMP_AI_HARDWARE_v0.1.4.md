# JAMP-AI-HARDWARE-v0.1.4

Implementation contract for immutable Conflict Records.

## Canonicalization

C14N-v0.1.4 is: schema-valid JSON, finite numbers only; timestamps normalized to UTC with exactly six fractional digits and `Z`; object keys lexicographically sorted; array order preserved; UTF-8 JSON with no insignificant whitespace and no NaN/Infinity.

The stored `conflict_id` is excluded from the hashed material. `evidence_a` and `evidence_b` are sorted by `artifact_sha256`, making the pair symmetric.

## Deterministic rules

- Equal observations: no conflict record.
- Same artifact SHA: duplicate evidence, no conflict.
- Different subject identity: different scope, not contradiction.
- Any mutation of immutable material changes `conflict_id`.
- Source precedence never silently mutates or deletes evidence. Predicate resolution remains fail-closed unless an explicit authoritative binding exists.
- An unresolved Conflict Record forbids VERIFIED.

## Test vectors

T01 A/B conflict: P4, false vs true -> `INCONCLUSIVE_EVIDENCE_CONFLICT`.
T02 reorder A/B -> identical conflict_id.
T03 duplicate -> no Conflict Record.
T04 scope mismatch -> `DIFFERENT_SCOPE` / `INCONCLUSIVE_INSUFFICIENT_EVIDENCE`.
T05 tamper -> stored conflict_id fails verification.
T06 authoritative vs self-attestation -> authoritative evidence only controls resolution when an explicit predicate binding exists; otherwise conflict remains inconclusive.

This contract is implementation-only until terminal CI evidence exists.
