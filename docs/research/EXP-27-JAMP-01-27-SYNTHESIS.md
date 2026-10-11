# JAMP Research Synthesis — Experiments 01–27

Status: RESEARCH SYNTHESIS / NON-NORMATIVE
Scope: consolidate the accumulated evidence trajectory of JAMP without changing Frozen Core or existing normative contracts.

## Executive result

Across the research sequence, JAMP progressed from reproducible search/execution traces to a layered provenance architecture covering execution, replay, prediction, causal events, evidence, tamper resistance, contingency, atomic observations, graph structure, ingestion scaffolds, AI/harness observation, policy/tool boundaries, runtime traces, and multi-agent trace comparison.

The central architectural result is the separation of two axes:
- Content determinism: intrinsic execution/evidence content can be canonically represented and deterministically hashed.
- Causal/lineage determinism: the current Frozen Provenance Contract v0 does not normatively require execution identity to be a deterministic cryptographic function of parent/lineage context.

This is an architectural/specification gap, not evidence that a real lineage exploit occurred.

## Research trajectory

### EXP-01–03 — search and transfer
The early experiments established reproducible search/transfer structures. The canonical evidence index records EXP-02 as PARTIAL TRANSFER and EXP-03 as B — TARGET PASS.

### EXP-04 — execution artifact
Demonstrated a bounded 4-Queens execution with a reconstructible artifact while preserving the Frozen Run Core. Later B-audit evidence recorded PASS — RECONSTRUCTIBLE.

### EXP-05 — stochastic environment boundary
Demonstrated bounded agent/environment interaction with explicit intended action versus actual environment outcome. Recorded outcome: TARGET PASS; B-audit: PASS — RECONSTRUCTIBLE.

### EXP-06 — parallel frontier
Demonstrated bounded threaded parallel-frontier execution, causal DAG canonicalization, logical replay, and Core immutability. Recorded outcome: CLOSED — TARGET PASS.

### EXP-07 — replay
Demonstrated deterministic log reconstruction without worker execution. CI run 35056249176: success; 5 passed. Recorded outcome: CLOSED — PASS.

### EXP-08–12 — provenance foundation
This stage established the specification/freeze boundary and then separated prediction, execution start/result, evidence, causal ordering, merge properties, and tamper resistance. The causal chain became:
PredictionRecord → PredictionCommit → ExecutionStart → ExecutionResult → EvidenceRecord
The normative boundary remained: provenance is not truth.

### EXP-13–16 — contingency and causality
Contingency/JUMP was formalized and connected to provenance DAG and evidence. The research boundary preserved the distinction between an unexpected event and a semantic success claim.

### EXP-17 — evidence conflict and synthesis
Visual evidence provenance, evidence conflict/reconciliation, and synthesis were introduced. Conflicting evidence remains INCONCLUSIVE; confidence alone does not promote evidence to SUPPORTED.

### EXP-18 — atomic observation
Atomic Observation Decomposition and lossless reconstruction established a research path from complex observations to immutable atomic observations and back to the canonical structural representation.

### EXP-19 — observation graph and scale
Observation adjacency/topology, subgraph views, synthetic scale, memory attribution, and optimization harnesses were measured separately. Measurements were not silently promoted into universal complexity or SLA claims.

### EXP-20–22 — ingestion and atomic integrity
Text/transcript normalization, provenance binding, AtomicObservation identity, source separation, payload sensitivity, transcript boundaries, and atomicity were tested in research-only scaffolds. Semantic verdicts remain outside atomization.

### EXP-23 — AI/harness observation
AI/harness observations were represented with model identity/version, harness identity/version, tool surface/policy, attempt index, inputs/outputs, and provenance. The observation digest binds the execution envelope without assigning a semantic verdict.

### EXP-24 — policy/tool provenance
Policy identity/version, tool surface, permission shifts, and provenance became explicit digest-bound research observations.

### EXP-25 — runtime trace provenance
Deterministic fixture traces bound runtime event streams to upstream policy/tool and AI lineage references, including sequence/order sensitivity.

### EXP-26 — multi-agent trace comparison
Deterministic trace streams were compared structurally using lineage, event order, event kind, and payload digests. Lineage mismatch is treated as a structural validation failure.

### EXP-27 — causal blind spot
The audit of Frozen Provenance Contract v0 and the make_execution() implementation identified a boundary:
- execution_hash is derived from intrinsic execution content: plan/question/parameters/observations/trace/state.
- The contract requires execution_id, but does not specify a deterministic construction rule that cryptographically binds it to parent_ref or an equivalent causal-graph identifier.
- Therefore content integrity/determinism and causal/lineage binding are distinct properties.
- No real graft/context-switch incident was demonstrated.

## Architectural result

JAMP now has a research vocabulary and evidence path for distinguishing:
1. what was predicted;
2. what was executed;
3. what was observed;
4. what evidence was produced;
5. what conflicts occurred;
6. how observations can be atomized and reconstructed;
7. how execution traces relate across agents;
8. and where lineage binding is or is not normative.

The remaining question is deliberately left open:
> Should causal lineage become part of the cryptographic execution identity, or should lineage remain a separately bound provenance layer?

This document does not answer that question and does not authorize a Frozen Core or contract mutation.

## Evidence boundary

This synthesis is a research summary, not a new normative contract. Existing experiment-specific evidence remains authoritative for individual results.

Repository invariants:
- Frozen Core remains unchanged.
- No runtime/production implementation change is introduced by this document.
- The document does not convert research findings into acceptance criteria.
- The EXP-27 finding is an architectural gap, not an observed exploitation event.