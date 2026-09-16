# JAMP Verification Framework Architecture

**Status:** Architectural companion specification  
**Baseline:** `main` at `4e6f6202cf643af3e607f451f198080aea954c89`  
**Evidence policy:** Evidence-First / auditable provenance

## 1. Introduction and epistemic scope

JAMP separates structural verification from empirical domain truth. The verification framework can establish that states, candidates, evidence references, lineage, and recorded measurements satisfy defined structural contracts. It cannot, by those measurements alone, establish that a mathematical hypothesis is true or that a discovery has occurred.

The governing principle is **honest incompletion**: an experiment that has not been executed remains `NOT EXECUTED`; a gate blocked by a missing prerequisite remains `BLOCKED`. Neither state may be converted into success or failure by inference, synthetic data, or narrative completion.

The architecture therefore provides an **auditable barrier** between what the software can verify internally and what requires authentic domain execution.

## 2. Five-tier architecture

### Tier 1 — Structure (P19, P22.1)

This tier provides immutable search-state structures, deterministic canonicalization and content-addressed identity. State hashes are derived from canonical representations using SHA-256, while runtime-dependent metadata is excluded by the structural contract. Search-state invariants include depth, causal-root, evidence-root, and constraint relationships.

These mechanisms establish structural identity and replay-oriented determinism. They do not establish mathematical truth.

### Tier 2 — Measurement (P22.2, P22.4)

Candidate generation enumerates structurally admissible descendants without ranking or selecting them through a heuristic objective. Candidate validation and evaluation produce raw structural measurements anchored to verified state identity.

The framework explicitly excludes hidden ranking, optimization, Bayesian selection, solver-style utility functions, and external numerical or machine-learning stacks from this structural layer. The absence of such mechanisms is an architectural constraint, not a claim that arbitrary future software can never contain them.

### Tier 3 — Evidence & Provenance (P21, P22.3)

This tier preserves parent-child lineage, content-addressed records, evidence roots, causal roots, and state anchors. Validation checks that derived records remain bound to their declared ancestry and that referenced identities are internally consistent.

Provenance integrity is evidence about the computational record. It is not a substitute for independent verification of the truth of a domain proposition.

### Tier 4 — Domain Execution (P25.4)

P25 defines a target experimental boundary for transfer from the √2 domain to √3. The domain-specific executor required for legitimate execution is currently unavailable with sufficient cryptographic provenance.

**Status: BLOCKED 🔒 / NOT EXECUTED.**

No sibling artifact, normalized or mangled text representation, inferred implementation, proxy, or synthetic reconstruction may substitute for the missing authentic raw-byte executor. Unblocking requires an authentic byte stream with verifiable SHA-256 identity, followed by independent AST and lineage/differential verification.

### Tier 5 — Claim Boundary (P25.5, P25.6)

Claims about empirical transfer or mathematical generalization require execution evidence. Structural metrics may demonstrate that the verification pipeline operated consistently; they do not constitute proof of the P25 hypothesis.

Consequently, no P25 success rate, failure rate, discovery claim, or generalization claim is asserted while execution remains unavailable.

## 3. Provenance ledger and unblocking protocol

Any future domain executor must pass the following sequence:

1. Obtain the authentic raw-byte stream.
2. Compute and record its SHA-256 identity.
3. Verify that the bytes parse as the expected executable artifact, including AST-level inspection where applicable.
4. Establish historical and repository lineage without reconstructing missing history.
5. Perform independent differential analysis against known related artifacts.
6. Freeze the verified executor identity and provenance record.
7. Only then permit experimental execution and capture of raw execution evidence.

A failure at any prerequisite preserves the gate as `BLOCKED`; it does not authorize approximation.

## 4. Anti-patterns and prohibitions

The following shortcuts violate the Evidence-First contract:

- proxy substitution for a missing primary artifact;
- synthetic reconstruction of historical source;
- hashing normalized, mangled, or otherwise transformed text as though it were the original bytes;
- treating a sibling file as the primary artifact;
- converting structural scores into solver success;
- inferring an unexecuted experiment from architectural readiness;
- introducing hidden heuristic selection or external optimization into a structural measurement layer;
- asserting generalization without the required execution evidence.

## 5. Epistemic status vocabulary

| Status | Meaning |
|---|---|
| `VERIFIED` | A defined structural or integrity property has sufficient evidence. |
| `SPECIFIED` | A protocol or requirement has been formally described but not experimentally established. |
| `NOT EXECUTED` | The specified experiment has not been performed. |
| `BLOCKED` | A required prerequisite is absent, so execution is not legitimately permitted. |
| `SUPPORTED` / `FALSIFIED` / `INCONCLUSIVE` | Outcomes of an actually executed investigation, subject to its declared evidence and claim boundary. |

`NOT EXECUTED` is not equivalent to `FAILED`.

## 6. Frozen baseline

The present baseline treats the P19–P22.4 verification infrastructure as the verified structural foundation and P25 domain execution as an explicitly unexecuted, blocked research target. The repository state must remain separable from unproven experimental conclusions.

The framework's central engineering commitment is therefore simple:

> **When evidence ends, the system stops rather than manufactures completion.**

This document describes the verification boundary and its intended safeguards. It does not claim empirical discovery capability beyond the evidence actually recorded by the project.
