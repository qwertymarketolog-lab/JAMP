# EXP-08 — Mutation Corpus

**Status:** FROZEN  
**Parent experiment:** EXP-08 Mutation Resistance  
**Specification:** frozen EXP-08 contract, blob `c505ffd1ca0a2e7071313c95b6d8a75b19ac5641`  
**Baseline:** EXP-07 Replay R0 verified implementation at commit `e241872ab3ed12d09a050e46c6259082e745ab0e`

## 1. Purpose

This document defines the deterministic mutation corpus for EXP-08. It specifies the controlled mutations to be applied to the recorded replay log used by EXP-07 Replay R0.

The corpus is an experimental input definition only. It does not contain observed results and does not assign PASS/FAIL verdicts in advance.

Lifecycle:

`DRAFT → REVIEWED → FROZEN → IMPLEMENTED → EXECUTED → EVIDENCE → PUBLISHED`

No mutation implementation or mutation test is part of this artifact.

## 2. Exact baseline

The baseline recorded log is the fixed four-event log defined by `tests/research/test_exp07_replay_r0.py` at baseline commit `e241872ab3ed12d09a050e46c6259082e745ab0e`.

Relevant immutable references:

- Frozen EXP-08 specification blob: `c505ffd1ca0a2e7071313c95b6d8a75b19ac5641`
- EXP-07 replay implementation blob: `3094a3fac59e712a556d32918946defe70aa5eb7`
- EXP-07 replay test blob: `7bdb5ff7300682b743ce57c2085e9c3604623930`
- EXP-06 adapter blob: `4654c19abe7038830b109531de7105f65defb06e`
- Frozen core blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Baseline canonical DAG hash: `a932483abc58e7f71c1f14859f270181a2b05f8d2d967840b6e9d21b4baddd75`

The baseline event definitions are:

| Event | Parents | Type | Worker | Clock | Payload |
|---|---|---|---|---:|---|
| `evt_P` | `()` | `FORK` | `coordinator` | 1 | `Parent root initialized` |
| `evt_WORKER_A` | (`evt_P`,) | `WORKER_COMPLETION` | `worker_a` | 2 | `Result=20` |
| `evt_WORKER_B` | (`evt_P`,) | `WORKER_COMPLETION` | `worker_b` | 2 | `Result=40` |
| `evt_M` | (`evt_WORKER_A`, `evt_WORKER_B`) | `JOIN` | `coordinator` | 3 | `Merged=60` |

For physical-order mutations, event identity and all event fields remain unchanged; only the order of the recorded event tuple is changed.

## 3. Reaction categories

Each executed mutant is classified only by the observed reaction:

- **A — Observable Difference:** replay succeeds, but canonical events, DAG hash, or merged result differs from the baseline.
- **B — Structural Rejection:** replay raises the structural error defined by the implementation/contract for the mutated input.
- **C — Silent Acceptance:** replay succeeds without a significant observable difference from the baseline.
- **D — Unexpected Failure:** unexpected exception or behavior requiring separate analysis.

These categories are observational. This corpus does not preassign a final category to any mutant.

## 4. Mutation rules

All mutations are deterministic and single-purpose.

- M1 changes only `logical_clock`.
- M2 changes only physical order of the recorded event sequence.
- M3 changes only `parent_event_ids`.
- M4 changes only `payload`.
- M5 removes exactly one baseline event.
- M6 injects exactly one additional event.

Unless a mutation explicitly removes or injects an event, all non-targeted event fields remain byte-for-byte identical to the baseline definition above.

## 5. Corpus M1–M6

### M1 — Logical-clock mutation

#### `M1-CLOCK-A`

- Source event: `evt_WORKER_A`
- Exact mutation: `logical_clock: 2 → 1`
- All other fields: unchanged
- Observable surfaces: replay success/rejection, canonical event order, DAG hash, merged result
- Allowed reaction categories: A / B / C / D

#### `M1-CLOCK-B`

- Source event: `evt_M`
- Exact mutation: `logical_clock: 3 → 2`
- All other fields: unchanged
- Observable surfaces: replay success/rejection, canonical event order, DAG hash, merged result
- Allowed reaction categories: A / B / C / D

### M2 — Physical/event-order mutation

#### `M2-REVERSE`

- Source: complete baseline recorded event sequence
- Exact mutation: reverse the physical order of all four recorded events
- Event set: unchanged
- Event fields: unchanged
- Observable surfaces: canonical event sequence, DAG hash, merged result, replay success/rejection
- Allowed reaction categories: A / B / C / D

This mutation probes the existing canonicalization property independently of event content.

#### `M2-SHUFFLE`

- Source: complete baseline recorded event sequence
- Exact mutation: reorder the same four events to physical order `evt_M, evt_WORKER_B, evt_P, evt_WORKER_A`
- Event set: unchanged
- Event fields: unchanged
- Observable surfaces: canonical event sequence, DAG hash, merged result, replay success/rejection
- Allowed reaction categories: A / B / C / D

### M3 — Parent/DAG mutation

#### `M3-PARENT-REMOVE`

- Source event: `evt_M`
- Exact mutation: `parent_event_ids` changes from (`evt_WORKER_A`, `evt_WORKER_B`) to (`evt_WORKER_A`,)
- All other fields: unchanged
- Observable surfaces: replay success/rejection, canonical DAG hash, merged result
- Allowed reaction categories: A / B / C / D

#### `M3-PARENT-INJECT`

- Source event: `evt_M`
- Exact mutation: append non-existent parent ID `evt_NONEXISTENT` to `parent_event_ids`
- Resulting parents: (`evt_WORKER_A`, `evt_WORKER_B`, `evt_NONEXISTENT`)
- All other fields: unchanged
- Observable surfaces: replay success/rejection, canonical DAG hash, merged result
- Allowed reaction categories: A / B / C / D

### M4 — Payload mutation

#### `M4-WORKER-PAYLOAD`

- Source event: `evt_WORKER_A`
- Exact mutation: `payload: Result=20 → Result=21`
- All other fields: unchanged, including JOIN payload `Merged=60`
- Observable surfaces: replay success/rejection, canonical event representation, DAG hash, merged result
- Allowed reaction categories: A / B / C / D

#### `M4-JOIN-PAYLOAD`

- Source event: `evt_M`
- Exact mutation: `payload: Merged=60 → Merged=61`
- All other fields: unchanged
- Observable surfaces: replay success/rejection, canonical event representation, DAG hash, merged result
- Allowed reaction categories: A / B / C / D

### M5 — Event deletion

#### `M5-DELETE-WORKER`

- Source event: `evt_WORKER_A`
- Exact mutation: delete the complete `evt_WORKER_A` event from the recorded log
- Remaining JOIN reference to `evt_WORKER_A`: unchanged
- Observable surfaces: replay success/rejection, canonical events, DAG hash, merged result
- Allowed reaction categories: A / B / C / D

#### `M5-DELETE-JOIN`

- Source event: `evt_M`
- Exact mutation: delete the complete `evt_M` event from the recorded log
- Remaining event set: `evt_P`, `evt_WORKER_A`, `evt_WORKER_B`
- Observable surfaces: replay success/rejection and structural error
- Allowed reaction categories: A / B / C / D

### M6 — Event injection

#### `M6-INJECT-WORKER`

- Source: baseline event set
- Exact mutation: add one additional event:
  - `event_id = evt_WORKER_C`
  - `parent_event_ids = (evt_P,)`
  - `causal_type = WORKER_COMPLETION`
  - `worker_id = worker_c`
  - `logical_clock = 2`
  - `payload = Result=40`
- Existing baseline events: unchanged
- Observable surfaces: replay success/rejection, canonical events, DAG hash, merged result
- Allowed reaction categories: A / B / C / D

#### `M6-INJECT-JOIN`

- Source: baseline event set
- Exact mutation: add one additional JOIN event:
  - `event_id = evt_M2`
  - `parent_event_ids = (evt_WORKER_A, evt_WORKER_B)`
  - `causal_type = JOIN`
  - `worker_id = coordinator`
  - `logical_clock = 3`
  - `payload = Merged=60`
- Existing baseline events: unchanged
- Observable surfaces: replay success/rejection and structural behavior concerning JOIN cardinality
- Allowed reaction categories: A / B / C / D

## 6. Experimental neutrality

No mutant in this corpus carries a PASS, FAIL, supported, falsified, inconclusive, or preferred outcome.

The implementation and execution stages must consume this frozen corpus without silently changing mutation definitions. Any change to the corpus after freezing requires an explicit protocol decision and a new corpus revision.

## 7. Lifecycle boundary

Current status is **FROZEN**.

The reviewed corpus is now formally frozen as the deterministic input contract for EXP-08. The 12 mutations, their source fields, exact mutation operations, and observable surfaces are fixed for the next lifecycle stage.

Implementation of mutators and test code may begin only against this frozen corpus. Execution, evidence publication, and changes to `docs/research/evidence-index.md` remain out of scope until their respective lifecycle stages are reached.
