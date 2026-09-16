# EXP-08 — Mutation Resistance

**Status:** FROZEN  
**Parent:** EXP-07 Replay R0

## 1. Purpose

EXP-08 measures the actual sensitivity of the existing bounded Replay R0 implementation to controlled mutations of recorded replay events. It does not assume in advance that every mutation must be rejected.

The experiment distinguishes observable sensitivity from defensive rejection. A changed DAG hash is not, by itself, evidence of protective detection.

## 2. Baseline

The baseline is the verified EXP-07 implementation at commit `e241872ab3ed12d09a050e46c6259082e745ab0e`.

Exact baseline blobs:

- `tests/research/exp07_replay.py`: `3094a3fac59e712a556d32918946defe70aa5eb7`
- `tests/research/test_exp07_replay_r0.py`: `7bdb5ff7300682b743ce57c2085e9c3604623930`
- `tests/research/parallel_dag_adapter.py`: `4654c19abe7038830b109531de7105f65defb06e`
- `src/jamp/run.py`: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

The fixed canonical DAG hash used by the EXP-07 tests is `a932483abc58e7f71c1f14859f270181a2b05f8d2d967840b6e9d21b4baddd75`.

## 3. Observed R0 Contract

The current replay implementation:

1. canonicalizes recorded events by `(logical_clock, event_id, sorted(parent_event_ids), causal_type)`;
2. computes a SHA-256 DAG representation containing clock, event ID, parents, causal type, worker ID, and payload;
3. requires exactly one `JOIN` event;
4. returns canonical events, the DAG hash, and the payload of the unique `JOIN` as `merged_result`.

The current implementation does not explicitly validate parent-reference existence, logical-clock consistency, or full DAG topology.

These are observations about the current code, not claims about a universal replay contract.

## 4. Mutation Model

EXP-08 initially covers six controlled mutation classes:

- **M1 — Logical-clock mutation:** alter one or more `logical_clock` values.
- **M2 — Physical/event-order mutation:** alter the physical order of recorded events while preserving the event set.
- **M3 — Parent/DAG mutation:** alter `parent_event_ids`.
- **M4 — Payload mutation:** alter an event payload.
- **M5 — Event deletion:** remove a recorded event.
- **M6 — Event injection:** add a new recorded event.

The exact mutation corpus must be frozen before execution.

## 5. Reaction Categories

Each mutated corpus is classified using the following observable categories:

### A — Observable Difference

Replay succeeds, but one or more observable outputs differ: canonical events, DAG hash, or merged result.

This establishes sensitivity. It is not automatically evidence of defensive protection.

### B — Structural Rejection

Replay rejects the mutation through an expected structural condition. The currently known example is the requirement for exactly one `JOIN` event.

### C — Silent Acceptance

The mutation is accepted without a significant observable difference.

This is an observation about the current implementation, not automatically a failure of the experiment.

### D — Unexpected Failure

The mutation produces an exception or behavior outside the pre-defined expected surfaces. It requires separate analysis and is not automatically PASS or FAIL.

## 6. Sensitivity Matrix

| ID | Mutation | Observable surface | Expected pre-experiment property | Observed | Verdict |
|---|---|---|---|---|---|
| M1 | Logical clock | canonical order / DAG hash | Clock participates in canonical ordering and hash representation; rejection is not assumed | TBD | TBD |
| M2 | Physical/event order | canonical events / DAG hash / merged result | Reordering sibling worker events is canonicalized identically by the existing R0 contract | TBD | TBD |
| M3 | Parent/DAG | canonical events / DAG hash / replay acceptance | Parents participate in canonicalization/hash; explicit parent-existence validation is absent | TBD | TBD |
| M4 | Payload | DAG hash / merged result | Payload participates in hash; JOIN payload determines `merged_result` | TBD | TBD |
| M5 | Event deletion | JOIN count / outputs | Reaction depends on which event is deleted; deleting the sole JOIN is structurally significant | TBD | TBD |
| M6 | Event injection | JOIN count / outputs | Reaction depends on injected event type and fields; exactly-one-JOIN constraint is structurally significant | TBD | TBD |

The `Expected pre-experiment property` column describes the observed baseline contract and does not predetermine the experimental verdict.

## 7. No Premature Mutation Score

EXP-08 does not define a Mutation Score before the mutation corpus, observable surfaces, and verdict rules have been executed and reviewed.

In particular, a changed DAG hash is not equivalent to protective detection, and successful replay is not by itself evidence that a mutation is harmless.

## 8. Execution Rules

Before execution, freeze:

- baseline references and hashes;
- mutation definitions;
- mutation corpus;
- observable output surfaces;
- expected baseline properties;
- verdict rules.

Mutation definitions must not be changed in response to observed results.

Replay must use the saved event corpus and must not execute the original workers.

## 9. Verdict Rules

The final experiment may use `PASS`, `FAIL`, and `INCONCLUSIVE`, but these labels must be assigned according to pre-defined mutation-specific criteria rather than by whether an implementation happens to throw an exception.

No mutation is declared detected merely because its hash differs.

## 10. Out of Scope

EXP-08 does not establish:

- universal replay security;
- resistance to arbitrary Git-history tampering;
- complete DAG validation;
- resistance to every possible corruption mode;
- security properties beyond the bounded replay path under test.

## 11. Provenance Requirements

A completed EXP-08 requires, at minimum:

- the frozen specification commit and blob;
- the execution commit;
- exact baseline and mutation-corpus references;
- source/test blobs used for execution;
- CI run identifiers when CI is used;
- raw or otherwise independently inspectable evidence;
- an evidence commit;
- publication through `docs/research/evidence-index.md` according to the repository evidence-publication rule.

No experimental result becomes canonically published without its complete evidence chain.

## 12. Lifecycle

`DRAFT → REVIEWED → FROZEN → IMPLEMENTED → EXECUTED → EVIDENCE → PUBLISHED`

The current document is **FROZEN**. Its content must not be changed without an explicit protocol decision that creates a new specification revision.
