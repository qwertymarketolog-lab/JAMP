# EXP-07-SPEC: Independent Replay of Canonical Provenance Log

**Status:** DRAFT — R0 IMPLEMENTATION
**Parent experiment:** EXP-06 — Parallel Frontier & Asynchronous Completion Boundary
**Frozen Core blob SHA-1:** `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

---

## 1. Research question

Can a recorded provenance event log from the bounded EXP-06 parallel-frontier scenario be replayed independently, without executing the original frontier workers, while recovering the same canonical DAG identity and merged logical state?

The claim is deliberately bounded to the concrete EXP-06 provenance model. This experiment does not claim universal replay support for arbitrary event schemas, schedulers, distributed systems, or problem classes.

## 2. R0 boundary

R0 tests only replay of an already-recorded event log. It must not:

- invoke the EXP-06 worker implementation;
- start a thread pool;
- re-run the original search/frontier computation;
- mutate `src/jamp/run.py`;
- perform mutation/corruption testing (reserved for EXP-08).

The replay implementation may consume only the recorded causal events and deterministic replay rules.

## 3. Canonical scenario

The bounded log contains:

```text
P  : logical clock 1, FORK
WA : logical clock 2, WORKER_COMPLETION
WB : logical clock 2, WORKER_COMPLETION
M  : logical clock 3, JOIN
```

`WA` and `WB` are causal siblings. Their physical completion order may differ, but their logical clock remains `2`.

The expected join payload is `Merged=60`.

## 4. R0 acceptance criteria

### R0.1 — valid log replay

A valid recorded log is replayed into a deterministic replay result containing the canonical event sequence, canonical DAG hash, and merged logical state.

### R0.2 — physical-order invariance

Two logs differing only in the physical order of the independent sibling completion events must produce identical canonical DAG hashes and identical merged logical state.

### R0.3 — worker isolation

Replay must succeed when the EXP-06 worker execution path is replaced by a `RAISE_IF_CALLED` guard. The test must demonstrate that replay consumes recorded events rather than re-running workers.

### R0.4 — canonical reference identity

Replay of the canonical EXP-06 log must reproduce a fixed reference canonical DAG hash and `Merged=60`. The reference hash is derived from the canonical event representation used by EXP-06 and is recorded by the R0 test fixture; it is not inferred from replay output at runtime.

## 5. Core immutability gate

R0 is an external research-layer change. `src/jamp/run.py` must remain byte-for-byte represented by Git blob SHA-1:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Any change to the frozen Core invalidates the R0 implementation as a clean continuation of the protocol.

## 6. Methodological boundary

A passing R0 establishes only:

> Within the frozen EXP-06 causal event model, JAMP can independently reconstruct the canonical DAG identity and merged logical state from a recorded provenance log without executing the original frontier workers.

R1 will address structural causal validation. Mutation/corruption resistance is explicitly deferred to EXP-08.
