# EXP-22 Charter: Atomic Observation Integrity

## Historical Provenance and Routing

This experiment formalizes the Atomic Observation Integrity research vector. It explicitly routes historical artifacts to establish a clean evidence boundary:

- **Adopted Evidence (PR #99):** The six foundational atomicity invariants (determinism, mutation sensitivity, composite isolation, provenance survival, transcript boundaries, and semantic neutrality) are adopted as the core criteria for execution.
- **Adopted Governance Precedent (PR #102):** The strict boundary between semantic observation integrity and performance timing is enforced. EXP-22 evaluates atomicity independently; any EXP-19 timing constraints are explicitly out of scope.
- **Superseded Proposal (PR #96):** The original open proposal is superseded by this charter's formalized RED/GREEN states.
- **Excluded Lineage (EXP-21 Phase 3):** Phase 3 concluded as NOT_CONFIRMED. Its bounding and performance objectives are excluded from EXP-22 to prevent cross-contamination of research goals.

## RED State (Current Baseline)

At main baseline (462b1c16...), there is an evidence gap. The repository lacks a self-contained, reproducible evidence contract that independently proves the complete set of atomic-observation integrity invariants against the current runtime state.

## GREEN State (Target Verification)

The experiment achieves GREEN when a dedicated test suite reproducibly proves the following invariant set on the target commit:

- **Determinism:** Unchanged atomization yields identical identity hashes.
- **Payload Sensitivity:** Mutation of the atomic payload predictably alters identity.
- **Source Binding (Provenance):** The digest cryptographically binds the source to the payload.
- **Transcript Boundaries:** Mutation of boundary definitions changes the resulting identity.
- **Identity Separation (Composite Isolation):** Composite mutations do not mask unchanged components.
- **Semantic Neutrality:** The atomization payload contains no semantic evaluation verdicts (e.g., SUPPORTED/REJECTED).

## Frozen Core & Constraints

- **Invariant:** Δ src/jamp = 0. The production runtime is locked.
- **Isolation:** The evaluation harness must not fail due to EXP-19 timing guards.
