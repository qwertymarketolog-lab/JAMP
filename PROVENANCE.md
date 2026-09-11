# Cap Provenance Audit

**Status:** PROVISIONALLY FROZEN / PROVENANCE PENDING  
**STATUS: PROTOCOL LOCK ONLY — NOT A VALIDATION ARTIFACT**

**Protocol lock commit:** `49a5c86be320cab5f998001182e6a3ffa836ec1c`

Decisions in GATE 0–2 must refer to this exact protocol-lock commit, not to mutable current contents of this file.

## Scope

`cap = 0, 25, 50, ... , infinity`

## Frozen Baselines

- **B6 SHA-256:** `d163c1d2bb711903029dd507e05f19d67ed746eec34d802631694e04aa584567`
- **Canonical harness SHA:** `<PENDING — not yet audited>`
- **Config hash:** `<PENDING — not yet audited>`

## Excluded Results

- 76 steps
- all pre-freeze numerical results
- all results not reproducible through the canonical runner

## Invariant Tuple

The provenance tuple is frozen as the following ordered fields:

`SHA`
`config_hash`
`seed`
`root`
`N`
`max_objects`
`cap`
`RNG_state`
`state_hash_at_intervention`
`pool_before_cap_hash`
`pool_after_cap_hash`
`ranked_order_hash`
`chosen_index`

This tuple is the protocol baseline for GATE 0–2. Any addition, removal, or semantic change to a tuple element is a protocol change and must be recorded by a new commit explicitly stating that the protocol was amended before GATE 0 passed.

## GATE 0 — Provenance

**PASS iff:** every required provenance field in the invariant tuple is recorded from the canonical execution path, with the target baseline and configuration independently identifiable and no field inferred or reconstructed from an unverified source.

**FAIL iff:** any required field is missing, ambiguous, inferred, or cannot be tied to the exact execution artifact being audited.

## GATE 1 — Cap Semantics

**PASS iff:** `cap` has one explicit, deterministic meaning in the canonical runner and the before/after cap pools are observable and hashable at the intervention point.

**FAIL iff:** cap semantics depend on hidden state, implicit ordering, undocumented behavior, or cannot be reconstructed from the recorded execution.

## GATE 2 — Cap Placement

**PASS iff:** the exact intervention point at which `cap` is applied is fixed, observable, and identical across compared runs; the invariant tuple records the state immediately relevant to that intervention.

**FAIL iff:** cap is applied at an ambiguous or moving point, or its placement can change the candidate pool/ranking without being represented in provenance.

## GATE 3 — Causal DAG

Required after GATE 0–2.

## GATE 4 — Ranking

Required after GATE 3.

## Exit Rule

Once GATE 0–2 pass, proceed to GATE 3/4.

No additional provenance constraints are added unless a concrete new failure mode is observed.

## Interpretation

The recursive application of JAMP principles to its own experimental procedure is an observation/illustration, not evidence that JAMP's methodological validity has been established.

## Execution Lock

While this status remains **PROVISIONALLY FROZEN / PROVENANCE PENDING**:

- new cap-series experiments are blocked;
- numerical results are not promoted to evidence merely by repetition;
- changes to the provenance contract require a concrete, observed failure mode;
- the next unblock condition is access to and audit of the canonical code/harness sufficient to evaluate GATE 0–2.

This document records the audit boundary; it does not itself establish PASS for any gate.

## Protocol-Lock Integrity

The exact protocol locked by commit `49a5c86be320cab5f998001182e6a3ffa836ec1c` had GitHub blob SHA `4ca7d2a0bc4b090059119e9d74b0de92e59ac7c9` for `PROVENANCE.md`.

This subsequent commit adds only explicit lock-status metadata and the protocol-amendment rule; it does not retroactively alter the meaning of the original lock.

The present file is a post-lock status supplement; the protocol anchor remains commit `49a5c86be320cab5f998001182e6a3ffa836ec1c`.

## JAMP Origin Framework

This section records the current methodological framework for provenance of JAMP itself. It is separate from the cap audit protocol above and does not establish historical facts that have not yet been evidenced by dated primary artifacts.

### Four layers

1. **Idea prehistory.** The broad position that the path to discovery/problem solving matters, not only the final result. This belongs to a wider intellectual tradition and is not, by itself, a distinctive JAMP origin claim.
2. **JAMP Core — operationalization.** The transformation of that position into an experimentally addressable mechanism: a search/representation space together with a dynamic transition in which an exhausted or ineffective mode (`STUCK`) leads to a change of representation/mode (`JUMP`).
3. **Engineering evolution.** Implementations and experiments derived from the core, including Cube, controlled experiments, R/D, Δ, registries, event/provenance DAGs, and later architecture.
4. **Audit protocol.** Provenance locks, invariant tuples, GATE 0–4, SHA fixation, causal ablation, and explicit separation of evidence, hypothesis, and reconstruction. This is a corrective methodology for making claims about JAMP auditable; it is not treated as a generative continuation of the JAMP mechanism.

### Core Birth — stopping criterion

For historical search purposes, **JAMP Core Birth** is defined as the earliest *dated primary artifact* in which both conditions are present:

- the path to a solution/discovery is treated as the object of study rather than only the final result; and
- a **dynamic STUCK → JUMP element** is present together with some explicit representation/search-space formalism.

The second condition is intentionally stronger than the presence of any single item from `{Ω, A, C, O, STUCK, JUMP, elements of thought}`. `Ω/A/C/O` alone can describe generic search or decision-process formalisms, and taxonomies of operations can have substantial prior art. The stopping criterion therefore requires the distinctive dynamic transition plus a space/representation formalism.

If no dated primary artifact satisfying this criterion is recovered, the correct result is **Core Birth: reconstruction only; no primary evidence**, rather than an arbitrarily selected earlier document.

### Core Birth and Audit Birth are independent origins

**JAMP Core Birth** is a **generative event**: a construction appears that was not previously present in the project record.

**JAMP Audit Birth** is a **corrective event**: an audit procedure is introduced in response to a concrete failure such as instrumentation drift (`76` versus `456`). It constrains how claims about JAMP may be made; it does not mean that JAMP was generated a second time.

These are therefore maintained as two independent provenance trees with a shared present-day leaf, rather than as two points on one chronological "birth" scale.

### Evidence model for historical artifacts

An artifact does not receive one undifferentiated historical status merely because some of its claims are strong. Historical assessment is **claim × strength**.

For each artifact, assess independently at minimum:

| Claim | Strength to assess |
|---|---|
| Date of the artifact | primary / corroborated / reconstructed |
| Authorship or attribution | primary / corroborated / reconstructed |
| Relation to Cube implementation | established / probable / unresolved |
| Conceptual content | direct textual evidence / inferred |
| Causal priority relative to later mechanisms | established / probable / unresolved |

The artifact currently referred to as **“Критика куба”** is therefore not assigned a single blanket `A` or `A-minus` label. Its evidentiary status must be decomposed claim by claim. In particular, a reliable internal date could establish the date claim without establishing causal priority relative to the Cube implementation.

### Prior art and independence

Claims of independence are not treated as provable at the level of the broad idea of studying problem-solving paths. The relevant test is **operational independence of the concrete formalization**. This requires comparison against relevant prior traditions and formalisms, including search/planning, MCTS, program synthesis, inductive logic programming, and interactive theorem proving, as appropriate to the specific JAMP construction.

Until such comparative work is completed, the project must not claim historical or operational independence from prior art.

### Provenance status of the origin framework

The four-layer model, Core Birth stopping criterion, independent Core/Audit origin trees, claim-by-claim evidence model, and prior-art qualification recorded here are **methodological decisions of the current provenance work**. They do not retroactively turn reconstructed history into primary evidence.

## Cycle closure 2026-09-12

Issue #39 closed. Results:
- extension cycle: NEGATIVE
- phase 3: NOT EXECUTABLE on accessible history
- track-a characterization: VALID, scoped to `d1b3a8c7e0cb6a16fb2eafacc5509382cecbcc39`
- `|closure|=13`: not proven as a closure-only invariant
- Task 5: DEFERRED / BLOCKED ON ENVIRONMENT

Anchors:
- `49a5c86be320cab5f998001182e6a3ffa836ec1c`: provenance, integrity defect present
- `d1b3a8c7e0cb6a16fb2eafacc5509382cecbcc39`: characterization, CI-unattested

Protocol lock `49a5c86be320cab5f998001182e6a3ffa836ec1c` unchanged.
