# EXP-11 / R0.1 — Terminal-State Integrity Attack

## Objective

Attack the terminal `EVIDENCE_RECORD` state before adding any new causal semantics.

## First adversarial invariant

After a valid chain reaches `EVIDENCE_RECORD`, every attempt to append another causal event must be rejected with `CAUSAL_ORDER_VIOLATION` and must preserve ledger state atomically.

## Required chain

`GENESIS → PREDICTION_COMMIT → EXECUTION_START → EXECUTION_RESULT → EVIDENCE_RECORD`

## Attack

Attempt to append a second `PREDICTION_COMMIT` after `EVIDENCE_RECORD` using the current head as parent and the next sequence index.

## Expected result

- rejection code: `CAUSAL_ORDER_VIOLATION`
- `head_before == head_after`
- `event_count_before == event_count_after`
- rejected event is not present in the ledger
- no internal exception such as `KeyError`

This is a focused first attack, not an expansion of the R0.5 contract.
