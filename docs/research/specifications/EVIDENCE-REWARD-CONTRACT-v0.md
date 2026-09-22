# EvidenceReward v0 — Evidence-Bounded Learning Boundary

**Status:** Draft / Research Contract  
**Layer:** Evidence → Evaluation → Learning boundary  
**Baseline:** `main` at `14abfd3a2616bf7fd2bd4246e1d2a8a08ad3d3ff`  
**Frozen Core:** unchanged; `src/jamp/run.py` remains LOCKED at blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`  
**Scope:** documentation-only; no production implementation is authorized by this contract.

## 1. Purpose

EvidenceReward v0 defines the minimum JAMP contract for deriving a learning-relevant reward object from **verified, admissible Evidence**.

The contract establishes an explicit boundary:

```text
Evidence != Reward != Learning Signal
```

Evidence records what was observed and what can be proven about its identity and provenance. EvidenceReward is a deterministic derivative of admissible Evidence under a frozen Criterion. LearningSignal is a separate downstream contract that may reference a derived reward but may not mutate historical Evidence.

This contract does not establish empirical truth, model correctness, or authorization to update a policy/model.

## 2. Architectural position

```text
Observation
    ↓
AtomicObservation
    ↓
Evidence
    ↓
Provenance
    ↓
Verification
    ↓
Conflict / Admissibility
    │
    ├── INVALID ────────► STOP
    ├── INCONCLUSIVE ──► STOP
    │
    ▼
ADMISSIBLE EVIDENCE
    ↓
EvidenceReward
    │
    ├── derivation failure ─► STOP
    │
    ▼
LearningSignal
    ↓
Learning / RL
```

The EvidenceReward boundary is intentionally downstream of epistemic verification and upstream of learning.

## 3. Normative inputs

EvidenceReward v0 has four conceptual inputs.

### 3.1 Evidence references

`evidence_refs[]` MUST identify exact immutable Evidence objects.

Each reference MUST be content-addressed or otherwise cryptographically resolvable to one immutable identity.

The following are not valid substitutes for immutable identity:

- `latest_evidence`
- `current_state`
- `last_result`
- `model_output`

unless they resolve through an explicit immutable reference before reward derivation.

### 3.2 Frozen Reward Criterion

The derivation MUST reference:

- `criterion_ref`
- `criterion_version`
- `criterion_hash`

The Criterion MUST be frozen before the Evidence execution being evaluated begins.

The Criterion defines a deterministic mapping from admissible Evidence to the reward domain. It MUST NOT modify Evidence or historical provenance.

### 3.3 Provenance binding

The reward derivation MUST bind at minimum:

- the ordered/canonical set of `evidence_hashes`;
- `criterion_hash`;
- `derivation_rule_hash`;
- `source_execution_refs`, where applicable.

A canonical provenance identity MUST be derivable from these inputs:

```text
Reward.provenance_hash =
    H(
        canonical(evidence_hashes)
        || criterion_hash
        || derivation_rule_hash
        || canonical(source_execution_refs)
    )
```

Any change to an input identity MUST produce a different derived provenance identity.

Therefore:

```text
ΔEvidence       → ΔReward identity
ΔCriterion      → ΔReward identity
ΔDerivationRule → ΔReward identity
```

Hash equality establishes identity/integrity; it does not by itself establish logical correctness.

### 3.4 Admissibility state

Admissibility is a gate, not a numeric reward:

```text
ADMISSIBLE
INCONCLUSIVE
INVALID
```

- **ADMISSIBLE:** all mandatory prerequisites for deterministic reward derivation are satisfied.
- **INCONCLUSIVE:** available Evidence is insufficient for deterministic reward derivation under the frozen Criterion.
- **INVALID:** Evidence identity, provenance, verification, or another mandatory contract condition is violated.

Neither `INCONCLUSIVE` nor `INVALID` is a numeric reward value.

## 4. Formal derivation

The conceptual function is:

```text
R = Reward(E, C, A)
```

where:

- `E` is an immutable Evidence set;
- `C` is the frozen Reward Criterion;
- `A` is the verified admissibility/provenance state;
- `R` is the derived EvidenceReward object.

The function is defined only for:

```text
A == ADMISSIBLE
```

and a deterministic derivation under `C`.

If a mandatory condition is `UNKNOWN`, the derivation MUST NOT silently map that condition to a numeric reward.

```text
UNKNOWN → NO_REWARD
```

The contract therefore distinguishes **absence of a reward derivation** from a valid numeric reward of zero.

## 5. Reward object schema

The minimum normative shape is:

```text
EvidenceReward_v0:
  reward_value
  reward_domain

  evidence_refs[]
  evidence_hashes[]

  criterion_ref
  criterion_version
  criterion_hash

  derivation_rule_ref
  derivation_rule_hash

  source_execution_refs[]

  admissibility
  provenance_hash
  reward_hash
```

`reward_hash` MUST be derived from the canonical reward object excluding `reward_hash` itself.

The object is **derived**, not authored as an independent source of truth.

## 6. Provenance invariant

The following invariant MUST hold:

```text
Reward.evidence_hashes
    ==
canonical identity set of the Verified Evidence used for derivation
```

A reward MUST NOT be accepted merely because a human-readable description names a previous execution or result.

A verifier MUST be able to resolve every bound Evidence reference and recompute the relevant identity chain.

## 7. Conflict semantics

Conflicting Evidence MUST NOT be converted into a scalar merely to make the learning pipeline total.

Example:

```text
E1 → supports
E2 → rejects
```

If both are otherwise admissible but the frozen Criterion contains no deterministic conflict-resolution rule:

```text
CONFLICT
   ↓
INCONCLUSIVE
   ↓
NO REWARD
```

Therefore:

```text
CONFLICT != 0
CONFLICT != 0.5
CONFLICT != penalty
```

A scalar reward may be derived from conflicting Evidence only when the frozen Criterion explicitly defines a deterministic, provenance-preserving resolution semantics that covers that conflict state.

## 8. INCONCLUSIVE and INVALID semantics

The contract deliberately separates epistemic states from numeric values.

| State | Meaning | EvidenceReward emitted? |
|---|---|---|
| ADMISSIBLE | Deterministic derivation is permitted | Yes |
| INCONCLUSIVE | Insufficient/ unresolved Evidence for derivation | No |
| INVALID | Contract/provenance integrity failure | No |

In particular:

```text
INCONCLUSIVE != 0
INVALID != 0
```

A downstream learning system MUST NOT reinterpret the absence of EvidenceReward as a zero reward unless a separate, explicit LearningSignal contract authorizes that transformation.

## 9. Fail-closed rules

EvidenceReward MUST NOT be emitted when any mandatory condition fails, including:

- missing Evidence;
- missing or unresolved Evidence reference;
- invalid Evidence identity;
- hash mismatch;
- unresolved provenance;
- criterion missing;
- criterion version mismatch;
- criterion hash mismatch;
- derivation rule missing;
- derivation rule hash mismatch;
- nondeterministic derivation;
- verification failure;
- unresolved conflict;
- Criterion outside its covered domain;
- unknown state not covered by the frozen Criterion;
- post-hoc Criterion or derivation rule;
- source execution identity mismatch;
- inability to recompute the bound provenance chain.

The required behavior is:

```text
if not verified:
    REWARD = NONE
```

The following substitutions are forbidden by this contract:

```text
UNKNOWN → 0
UNKNOWN → penalty
UNKNOWN → fallback()
UNKNOWN → model_confidence
UNKNOWN → estimated reward
```

## 10. Determinism requirements

Reward derivation MUST be a pure deterministic function of its canonical inputs.

It MUST NOT depend on:

- wall-clock time;
- mutable global state;
- current repository state;
- `latest` or `current` aliases;
- model confidence;
- optimizer state;
- random sampling;
- unrecorded human judgment;
- hidden environment state.

Equivalent canonical input representations MUST produce identical reward identities and values.

## 11. Read-only and history preservation

EvidenceReward derivation MUST be read-only with respect to Evidence, provenance, Criteria, executions, and historical results.

The derivation MUST NOT:

- edit Evidence;
- replace Evidence;
- delete Evidence;
- rewrite provenance;
- retroactively alter a Criterion;
- rewrite an execution;
- mutate historical verdicts;
- feed a derived reward back into the historical Evidence ledger.

This preserves the existing JAMP evidence-bounded scoring and historical immutability boundary.

## 12. Evidence → Reward → Learning boundary

The responsibilities are explicitly separated.

### Evidence

Answers:

> What was observed, and can its identity and provenance be established?

### EvidenceReward

Answers:

> What deterministic evaluation signal follows from admissible Evidence under the frozen Criterion?

### LearningSignal

Answers:

> Is this derived reward permitted to participate in a particular learning/update protocol?

Therefore EvidenceReward MUST NOT contain or invoke:

```text
update_policy()
gradient()
loss()
optimizer()
model_update()
```

It terminates at:

```text
REWARD_DERIVED
```

## 13. LearningSignal boundary

LearningSignal is a separate contract.

A minimal downstream reference shape is:

```text
LearningSignal:
  reward_ref
  learning_policy_ref
  trajectory_ref
  action_ref
```

The LearningSignal MAY reference EvidenceReward and the execution trajectory. It MUST NOT mutate Evidence.

The transition:

```text
EvidenceReward → LearningSignal
```

requires a separate admissibility contract for learning. EvidenceReward alone does not authorize a policy/model update.

## 14. State machine

The normative EvidenceReward state machine is:

```text
RECEIVED
   │
   ├── missing/invalid identity ───────► INVALID
   │
   ▼
VERIFYING
   │
   ├── provenance failure ─────────────► INVALID
   ├── unresolved/insufficient state ──► INCONCLUSIVE
   ├── unresolved conflict ────────────► INCONCLUSIVE
   │
   ▼
ADMISSIBLE
   │
   ├── derivation failure ─────────────► INVALID
   │
   ▼
REWARD_DERIVED
   │
   ▼
LEARNING BOUNDARY
```

There is no transition:

```text
INCONCLUSIVE → REWARD_DERIVED
```

without new admissible Evidence or a new frozen Criterion version.

There is no transition:

```text
INVALID → REWARD_DERIVED
```

without repairing the invalid provenance/input state and performing a new deterministic verification.

## 15. Conformance invariants

A conforming EvidenceReward v0 implementation MUST satisfy:

1. **Evidence immutability** — Evidence is never modified by reward derivation.
2. **Content identity** — every Evidence input resolves to an exact immutable identity.
3. **Criterion freeze** — the applied Criterion is versioned and content-addressed.
4. **Deterministic derivation** — identical canonical inputs produce identical output.
5. **Provenance binding** — reward identity binds Evidence, Criterion, derivation rule, and applicable execution references.
6. **Conflict preservation** — unresolved conflict does not become a synthetic scalar.
7. **Fail-closed behavior** — mandatory UNKNOWN/invalid states prevent reward emission.
8. **No truth claim** — Reward does not establish empirical truth.
9. **No learning authorization** — Reward does not authorize policy/model updates.
10. **Historical immutability** — deriving a reward cannot rewrite prior Evidence or verdict history.

## 16. Relationship to existing scoring contracts

EvidenceReward v0 does **not** replace or silently modify existing JAMP scoring contracts.

In particular, an existing evidence-bounded scoring contract may define a valid scalar result such as `0.0` for a canonical empty-ledger case. EvidenceReward addresses a different boundary: whether a verified, admissible evaluation result may be emitted as a learning-relevant reward object.

Therefore:

```text
P22.x scoring semantics
    ≠
EvidenceReward admissibility semantics
```

A future implementation MUST explicitly bind the chosen scoring contract to EvidenceReward rather than infer that binding from numeric equality.

## 17. Non-responsibilities

EvidenceReward v0 does not define:

- an RL algorithm;
- a policy-update rule;
- a loss function;
- optimizer behavior;
- exploration strategy;
- reward shaping;
- a universal reward scale;
- empirical truth of a hypothesis;
- model quality;
- causal attribution beyond what the frozen Evidence/Verification contract establishes.

## 18. Freeze and implementation boundary

This document is a research contract only.

No production implementation is authorized by EvidenceReward v0.

Any implementation MUST first identify:

1. the concrete Evidence schema it consumes;
2. the concrete Criterion/Scoring contract it binds;
3. the canonical serialization and hashing procedure;
4. the verifier boundary;
5. the downstream LearningSignal contract;
6. executable acceptance tests for all fail-closed states.

A future frozen version MUST create a new versioned contract rather than mutate this v0 definition after it is frozen.

---

## Summary invariant

```text
Reward is a deterministic derivative of admissible Evidence.
Reward is not Evidence.
Reward is not Truth.
Reward is not Learning.
```

The learning boundary is therefore:

```text
AI Observation
   ↓
Evidence
   ↓
Provenance / Verification
   ↓
Admissibility
   ↓
EvidenceReward
   ↓
LearningSignal
   ↓
Learning / RL
   ↓
new Observation
```

The loop may create new observations and new Evidence, but it MUST NOT rewrite the Evidence history that produced prior rewards.
