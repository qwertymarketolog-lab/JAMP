# Q3b: neutral Artifact Contract v0

## Q3b.1 — Specification

Typed metadata:

- `artifact_version`
- `adapter`
- `adapter_contract` (optional)
- `run_result.steps`
- `run_result.iterations`
- `run_result.stop_reason.kind`
- `run_result.stop_reason.detail`

Opaque domain payload:

- `final_state`
- `provenance`

The Artifact Contract version is independent of the Run contract version.

Not claimed:

- third-domain neutrality;
- production exporter transfer;
- semantic equivalence of provenance across domains;
- minimal or canonical schema;
- stability across Run contract versions.

Status: **SPECIFIED — not experimentally validated at this stage**

## Q3b.2 — Implementation evidence

Implementation commit: `4b08da31b1f451b0e573060760ae5b99766f65a9`

Execution: `PYTHONPATH=src:. python -m pytest -q tests/research/test_artifact_v0.py`

Result: `2 passed in 0.29s`

Executed on:  <commit SHA not recorded>
              Local execution during development; no automatic
              attribution to a specific commit.

Adapter:      tests/research/track_a_run_adapter.py
              blob 7a3f0ac9e64b17da7a71dd66071329d8f98656a0
              (at implementation commit 4b08da31)

Verified: JSON round-trip; two distinct domain payload shapes; optional `adapter_contract`; independent Artifact Contract versioning.

Core unchanged: `src/jamp/run.py` blob SHA `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

## Q3b.3 — Production integration

Status: **PASS**

Implementation commit: `56218c31abad64fdda91f8789b7e7ff9d36bd7cf`

Execution: `PYTHONPATH=src:. python -m pytest -q tests/research/test_q3b3_production_integration.py`

Result: `1 passed in 0.96s`

Executed on:  <commit SHA not recorded>
              Local execution during development; no automatic
              attribution to a specific commit.
              Test file present at ed686f52; not equivalent to
              executed-on.

Adapters:     tests/research/track_a_run_adapter.py
              blob 7a3f0ac9e64b17da7a71dd66071329d8f98656a0

              tests/research/puzzle8_run_adapter.py
              blob f5f65aaaddc2e2c860a5838f45dc9c52d5624601
              (at normalization commit 56218c31)

Verified: real TrackAAdapter and Puzzle8Adapter use the same `run()` and `serialize_run_result()`; domain payloads are normalized before neutral serialization; JSON round-trip passes for both artifacts.

Core unchanged: `src/jamp/run.py` blob SHA `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

The integration does not make the neutral serializer domain-aware. Domain-specific normalization remains outside the neutral Artifact Contract.

Timing note:
  Session observation:  0.25s (Q3b.2), 0.74s (Q3b.3)
  This file records:    0.29s (Q3b.2), 0.96s (Q3b.3)
  Relationship between the two pairs: not established.
  Both are local execution timings; they are not attributed
  to different commits by any recorded evidence.

### Q3b status

- Q3b.1 — SPECIFIED
- Q3b.2 — PASS
- Q3b.3 — PASS

Overall: **Q3b CLOSED**

Not claimed: third-domain neutrality; universal artifact schema; semantic equivalence of provenance across domains; replacement or generalization of the existing Track-A-specific exporter.
