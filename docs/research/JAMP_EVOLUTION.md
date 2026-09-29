# JAMP Evolution

## Purpose

JAMP remains independent of any specific AI model, hardware platform, or input data format.

The proven JAMP core is the foundation. Further development proceeds through isolated research levels and experiments rather than by weakening or replacing established contracts.

The purpose of this document is to provide an architectural map for future research. It does not itself establish experimental results or close research hypotheses.

## Foundation

The current JAMP foundation is built around:

- **Ω — search space**
- **A — actions**
- **C — constraints**
- **O — observations**
- evidence-first experimentation
- explicit provenance
- conflict handling
- replay and auditability
- falsifiability
- explicit execution states
- controlled research branches
- separation of proven results from hypotheses and session-only observations

The guiding loop is:

**observation → question → controlled experiment → result → verification → next question**

JAMP is intended to preserve the evidence chain through this loop.

## Architecture stack

The current research architecture is organized as a progression from protected foundations to execution and replay infrastructure:

**Frozen Core → Evidence → Provenance → Conflict → Atomic Observation → Multi-AI Federation → Evidence Acquisition → Deterministic Qualification → Immutable Evidence Bundle → Offline Replay → Experiment Engine → Adaptive Research Loop → Research OS / Domain Products**

These are architectural levels, not separate JAMP versions. A level may remain in progress or HOLD while later contracts are being designed.

### Foundation

1. **Evidence** — observations, evidence records, deterministic artifacts, and explicit epistemic status.
2. **Provenance** — execution identity, source lineage, temporal consistency, and explicit binding to frozen specifications and criteria.
3. **Conflict** — contradictory evidence is preserved rather than silently resolved.
4. **Atomic Observation** — observations are decomposed into deterministic, traceable atomic records with preserved source provenance.

### Multi-AI Federation

Different AI models are treated as interchangeable research instruments rather than privileged sources of truth.

The current AnyModel v3 audit contains **87 models × 30 checks = 2,610 checks**. Capability qualification remains separate from provenance authentication.

### Evidence Acquisition & Replay

The current implementation direction is:

**Multi-AI audit → Execution Evidence Acquisition → Deterministic Checker & Qualification → Immutable Evidence Bundle → Offline Replay**

PR #225 defined the R18–R24 frozen-input contract. PR #226 added the Evidence Acquisition Contract v0 to main. The contract is design-only/pre-freeze; implementation must establish its own contract tests and terminal CI evidence before claiming conformance.

### Experiment Engine

Use JAMP to coordinate controlled experiments across models, data, transformations, parameters, and environments.

### Adaptive Research Loop

Allow subsequent research actions to depend only on verified observations and experimental results while preserving the evidence chain and preventing unsupported state changes.

### Research OS / Domain Products

The long-term target combines the verified evidence infrastructure into reproducible research workflows and domain-specific products without coupling those products to the Frozen Core.

## AI and hardware are tools

AI models are research instruments.

Data and files are research material.

Hardware is a compute environment.

JAMP is the research, evidence, provenance, conflict, and audit contour connecting them.

A new model, chip, quantization format, or input modality must not require changes to the proven core merely because it is new.

Any core change requires its own evidence and controlled experiment.

## Architectural rule

**Do not modify a proven contract to accommodate an untested capability.**

New capabilities should first enter through isolated research artifacts and tests.

Only evidence demonstrating that an architectural change is necessary and justified can support a subsequent core change.

## Current Experimental & Architecture State

### Verified foundations

- **Frozen Core invariant:** src/jamp/run.py remains at blob 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a; Δ = 0.
- **Evidence:** canonical evidence commitments and deterministic artifacts are established.
- **Provenance:** historical AnyModel v3 evidence is temporally consistent, while execution binding remains **HOLD / unresolved**.
- **Atomic Observation:** deterministic observation identity is established without changing the Frozen Core.
- **Multi-AI audit:** AnyModel v3 contains 87 models × 30 checks = 2,610 observations/checks.

### Current focus: Evidence Acquisition & Deterministic Qualification

- The former “next step: Atomic Observation Decomposition” marker is obsolete; Atomic Observation is now an established foundation layer.
- **R18–R24 Frozen-Input Contract:** defined in PR #225.
- **Evidence Acquisition Contract v0:** merged in PR #226; design-only/pre-freeze.
- **AnyModel qualification:** **INCONCLUSIVE / HOLD**; 25 candidates remain blocked by mandatory P0 evidence.
- **Next tactical target:** implement the deterministic checker runtime, immutable evidence bundle generation, and offline replay without modifying the Frozen Core.

### Current State Matrix

| Component | Status | Evidence boundary |
|---|---|---|
| Frozen Core | VERIFIED / FROZEN | src/jamp/run.py blob 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a; Δ = 0 |
| Evidence System | VERIFIED | Canonical records and content commitments |
| Provenance Tracking | VERIFIED / HOLD | Temporal consistency verified; execution binding unresolved |
| Conflict Handling | VERIFIED | Contradictions remain explicit |
| Atomic Observation | VERIFIED | Deterministic observation identity |
| Multi-AI Federation / AnyModel v3 | VERIFIED / ONGOING | 87 × 30 = 2,610 checks |
| AnyModel Qualification | INCONCLUSIVE / HOLD | 25 candidates blocked on mandatory P0 evidence |
| R18–R24 Frozen-Input Contract | DEFINED | PR #225 |
| Evidence Acquisition Contract v0 | MERGED | PR #226; design-only/pre-freeze |
| Execution Implementation | NOT YET IMPLEMENTED | Next working stage |
| Replay Engine | NOT YET IMPLEMENTED | Depends on executable evidence bundle/checker |
| Adaptive Research Loop | ACTIVE DEVELOPMENT | Infrastructure/control layer |
| Research OS / Domain Products | ROADMAP | Future target |


## Research discipline

For each new level, the preferred sequence is:

**SPEC → RED tests → reference operator → GREEN → CI → evidence → DECISION**

Research status must remain grounded in actual artifacts, commits, test output, and CI evidence.

This document is an architectural roadmap. It does not substitute for those results.

## Non-negotiable boundary

The proven JAMP core remains frozen unless a separate, evidence-backed research process demonstrates that a change is required.

The evolution of JAMP therefore proceeds outward from the foundation rather than by repeatedly rewriting the foundation.
