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
