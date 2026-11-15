# JAMP Audit v1 — AMBIGUOUS Protocol

## Boundary

The harness performs no semantic similarity, cross-model claim matching, or LLM judging. It never decides that two model statements concern the same proposition.

## Human matching

In the first audit iteration, a human reviewer inspects original responses and claim records, decides whether two claims concern the same proposition, assigns the same reviewer-controlled canonical claim_id, and explicitly records whether they contradict.

Different claim sets are independent observations, not conflicts. Three models returning three different claim sets does not create AMBIGUOUS.

## Conflict types

- claim_vs_claim: a human has matched two model claims to the same canonical claim and determined that their statements contradict.
- claim_vs_evidence: a human has identified a contradiction between one claim and a specific primary evidence record.

A conflict record contains conflict_id, canonical claim_id, conflict_type, participants, optional evidence_id, status AMBIGUOUS, resolution null, and resolved_by null.

## Resolution

AMBIGUOUS remains unresolved until a human reviewer records a separate resolution using resolution.schema.json, with reviewer identity, rationale, timestamp, and evidence references. A majority vote is not a resolution. Model consensus is not evidence.

The harness may validate the shape and evidence references of a human resolution. It does not decide which claim is true. Conflicts and original model responses are preserved; no source statement is overwritten or silently dropped.
