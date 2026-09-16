# EXP-07 Evidence — Replay R0

**Status:** CLOSED — PASS  
**Protocol:** Replay R0  
**Frozen Core blob SHA-1:** `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

## 1. Implementation provenance

- Execution commit: `e241872ab3ed12d09a050e46c6259082e745ab0e`
- Adapter restored from EXP-06 without content change; blob SHA-1: `4654c19abe7038830b109531de7105f65defb06e`.
- Replay implementation blob SHA-1: `3094a3fac59e712a556d32918946defe70aa5eb7`.
- Test blob SHA-1: `7bdb5ff7300682b743ce57c2085e9c3604623930`.
- Workflow blob SHA-1: `3dad7dd31ffb830e51c495a1bf30e168d5d96307`.
- The frozen Core file `src/jamp/run.py` was not modified by the EXP-07 change set and its expected Git blob SHA-1 is asserted by the R0 test.

## 2. R0 protocol result

### R0.1 — Log integrity

**PASS.** Replay accepts the recorded event log and reconstructs the expected canonical event sequence and merged result `Merged=60`.

### R0.2 — Deterministic reconstruction

**PASS.** The same logical event set is supplied in two physical worker orders. Replay canonicalizes both to the same event sequence and requires identical DAG hashes and merged result.

### R0.3 — No worker execution

**PASS.** The test first captures a recorded log from the EXP-06 adapter, then replaces `ParallelDAGAdapter._worker_task` with a guard that raises if called. Replay succeeds from the recorded log, proving the replay path does not execute the worker task.

### R0.4 — Provenance preservation

**PASS.** Replay returns the complete canonical event sequence and computes the canonical DAG hash from event clocks, IDs, parent IDs, causal types, worker IDs, and payloads. The fixed expected DAG hash is `a932483abc58e7f71c1f14859f270181a2b05f8d2d967840b6e9d21b4baddd75`.

### Frozen Core immutability

**PASS.** The R0 test computes the Git blob SHA-1 of `src/jamp/run.py` and requires `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

## 3. CI evidence

Dedicated GitHub Actions workflow: `EXP-07 Replay R0`.

- CI run: `35056249176`
- Event: `push`
- Branch: `research/exp-07-replay-r0`
- Head commit: `e241872ab3ed12d09a050e46c6259082e745ab0e`
- Job: `replay-r0`
- Conclusion: `success`
- Pytest result: `5 passed in 0.04s`

The CI log shows checkout of the exact execution commit, Python 3.11 setup, `PYTHONPATH: src`, execution of `python -m pytest -q tests/research/test_exp07_replay_r0.py`, and five passing tests.

## 4. Scientific / protocol conclusion

**PASS — CLOSED.**

Within the bounded R0 protocol, a recorded causal event log can be replayed deterministically without rerunning its worker task, while preserving the canonical event/DAG representation. The result is additionally gated by frozen-Core immutability.

This evidence establishes the tested Replay R0 protocol only. It does not establish universal replayability for arbitrary logs, schedulers, distributed systems, or problem classes.
