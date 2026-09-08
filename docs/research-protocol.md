# JAMP Research Protocol

## Purpose

JAMP is intended to study machine discovery as an auditable experimental process. The system must preserve not only the final result but the path by which the result was obtained.

## Discovery principle

Do not fit a mechanism retrospectively to a known answer. A research artifact should reconstruct the available observation, question, hypotheses, actions, failed attempts, causal relationships and resulting state transitions.

A known solution may be used as an external validation target, but it must not be silently injected into the mechanism being tested.

## Evidence contract

Every meaningful experiment should make it possible to identify:

- exact source and target code revision;
- experiment inputs and configuration;
- causal event history;
- state and evidence digests where applicable;
- deterministic ordering rules;
- replay result;
- CI test result;
- generated report and its digest when a report is part of the milestone;
- ablation result when the claim is causal necessity.

## Milestone gate

A milestone is GREEN only when the claimed behavior is supported by concrete telemetry tied to the exact implementation under evaluation.

No simulated CI result, inferred run, guessed SHA or reconstructed status may be used as evidence.

## Causal ablation

Regression is insufficient for a causal claim. When a mechanism is claimed to be necessary, the experiment must remove or disable that mechanism while keeping the relevant surrounding conditions stable and observe the predicted failure or breach.

For P18.4 the required ablations are authorization, isolation and digest validation. The expected breach must be observable and attributable to the removed guardrail.

## Reproducibility

Experiments should be replayable from their recorded inputs and immutable causal history. Deterministic tie-breaking, canonical serialization and cryptographic digests should be used where required to eliminate hidden nondeterminism.

## Boundary discipline

Research layers must not silently mutate lower-level core invariants. Search, policy and experimental orchestration remain above the domain-agnostic integrity and causal layers unless a milestone explicitly changes the contract and proves the change.
