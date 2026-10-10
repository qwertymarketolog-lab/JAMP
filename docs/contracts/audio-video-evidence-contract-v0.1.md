# Audio/Video Evidence Contract v0.1 — specification and isolated reference adapter

Status: OPEN / specification, synthetic fixtures, and isolated fail-closed audio adapter.

## Scope
This v0.1 increment includes the transport-neutral evidence-envelope specification, JSON Schema, deterministic synthetic test vectors, and a minimal isolated reference adapter at `src/jamp/audio/adapter.py`. The adapter applies fail-closed evidence checks for target identity, model-weight integrity, reported metrics, output completeness, and provenance. It does not connect to the existing JAMP runtime or API.

## Purpose
Define a transport-neutral evidence envelope for external audio/music and video analyzers. JAMP validates identity, schema, completeness, and provenance; it does not itself decode media or infer whether content is AI-generated.

## Files
- `schemas/audio-video-evidence-v0.1.schema.json`: JSON Schema Draft 2020-12.
- `test-vectors/audio-video-evidence-v0.1.json`: deterministic synthetic cases.
- `src/jamp/audio/adapter.py`: minimal isolated fail-closed audio adapter reference implementation.

## Gate semantics
- `VERIFIED`: schema is valid, target hash matches the independently computed digest, required metadata/metrics are present, and analyzer provenance is structurally complete. This verifies the evidence procedure only—not the truth of an analyzer's classification.
- `REFUSE`: target digest mismatch or invalid schema/unsupported shape.
- `HOLD`: required analysis data is absent or not yet available. Schema validation alone will reject missing required fields; a gate adapter may classify a recognized incomplete/in-progress envelope as HOLD before final schema acceptance.
- `INCONCLUSIVE`: independently identified analyzer outputs conflict under a separately versioned conflict policy. Schema validity alone cannot decide conflict.

## Integrity requirements
1. Compute target and weights SHA-256 from the exact bytes supplied to inference; never trust a supplied digest by itself.
2. The reference adapter reads each input into a byte string, verifies its digest, and passes those same byte strings to the inference callback. It does not pass file paths for the callback to reopen, preventing a path replacement between verification and inference from changing the bytes consumed.
3. Every analyzer result must bind to the computed target digest.
4. Preserve each analyzer result separately; do not average or silently select a winner.
5. Keep raw output and normalized metrics distinct. If raw output is not available, record that limitation rather than synthesizing it.
6. The reference adapter requires non-empty analyzer tool ID/version, model version, and a timezone-aware ISO-8601 analysis timestamp before inference. This is structural provenance validation only: caller-supplied metadata is not independent proof that an analyzer actually ran.
7. Probability fields are analyzer-reported values, not calibrated or comparable across tools unless separately evidenced.
8. A timestamp is provenance metadata, not proof that an analyzer actually ran.
9. Test vectors are fixtures, not evidence of production detector accuracy.

## Boundaries and non-goals
- No real media decoding, production model weights, or external analyzer integration is included.
- No production audio/video detection capability or accuracy claim is made.
- The adapter is isolated; this increment does not integrate it into the existing JAMP runtime/API and does not change workflows.
- Synthetic fixtures and passing tests establish only the tested procedure, not real-world detector accuracy.

## Frozen Core
`src/jamp/run.py` is outside scope and must remain byte-for-byte unchanged at blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` (expected code delta = 0).
