# Evidence Index

This directory is the research evidence boundary for JAMP.

Evidence should be linked to exact implementation revisions and, where applicable, CI run IDs, experiment report digests and replay results.

## Current evidence baseline

### P16

Causal Event DAG, replay/time travel, deterministic causal ordering, Vector Clock and SHA-256 integrity are closed milestones.

### P17

P17.1 through P17.6 are closed. The sequence establishes deterministic evaluation, cross-session pattern indexing, adaptive policy, policy events and replay, policy-guided search, and a closed-loop deterministic experiment.

### P18

P18.1.2, P18.2 and P18.3 are closed. They establish the experiment registry bridge, zero-transfer task isolation and explicitly authorized cross-task transfer.

### P18.4

P18.4 remains pending verified CI. The production guardrail is locked and the exact target implementation SHA is:

`7b717a8dea269bc5c33d9c128634f55c0bad27b0`

Original target CI Run #165 / Run ID `34212659566` completed with `139 passed / 1 failed`. The failure was in the test fixture: authorization ownership was mismatched, so the intended authorization PermissionError branch was never reached.

The next evidence step is a test-only correction followed by a fresh CI run on the resulting exact SHA.

## Evidence rule

Never promote a milestone based on an unobserved CI run, a guessed commit SHA, a synthetic result, or a status inferred from code inspection alone.
