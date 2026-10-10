# Audio/Video Evidence Contract v0.1 — design boundary

Status: OPEN / design-and-fixtures only.

## Purpose
Define a transport-neutral evidence envelope for external audio/music and video analyzers. JAMP validates identity, schema, completeness, and provenance; it does not itself decode media or infer whether content is AI-generated.

## Files
- `schemas/audio-video-evidence-v0.1.schema.json`: JSON Schema Draft 2020-12.
- `test-vectors/audio-video-evidence-v0.1.json`: deterministic synthetic cases.

## Gate semantics
- `VERIFIED`: schema is valid, target hash matches the independently computed file hash, required metadata/metrics are present, and analyzer provenance is structurally complete. This verifies the evidence procedure only—not the truth of an analyzer's classification.
- `REFUSE`: target digest mismatch or invalid schema/unsupported shape.
- `HOLD`: required analysis data is absent or not yet available. Schema validation alone will reject missing required fields; a gate adapter may classify a recognized incomplete/in-progress envelope as HOLD before final schema acceptance.
- `INCONCLUSIVE`: independently identified analyzer outputs conflict under a separately versioned conflict policy. Schema validity alone cannot decide conflict.

## Integrity requirements
1. Compute target SHA-256 from the actual bytes at ingestion; never trust a supplied digest by itself.
2. Every analyzer result must bind to that computed target digest.
3. Preserve each analyzer result separately; do not average or silently select a winner.
4. Keep raw output and normalized metrics distinct. If raw output is not available, record that limitation rather than synthesizing it.
5. Probability fields are analyzer-reported values, not calibrated or comparable across tools unless separately evidenced.
6. A timestamp is provenance metadata, not proof that an analyzer actually ran.
7. Test vectors are fixtures, not evidence of production detector accuracy.

## Frozen Core
`src/jamp/run.py` is outside scope and must remain at blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` (expected code delta = 0).

## Non-goals
No real media decoding, no external analyzer integration, no runtime/API changes, no claim of audio/video detection capability, and no workflow changes in this design-only increment.
