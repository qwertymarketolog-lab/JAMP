# EXP-07-SCENARIOS: Replay R0 Test Scenarios

**Status:** DRAFT — R0 IMPLEMENTATION
**Target spec:** `docs/research/EXP-07-SPEC.md`
**Frozen Core blob SHA-1:** `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

---

## SCN-07-01 — Valid recorded log replay

**Input:** canonical recorded EXP-06 event log `P, WA, WB, M`.

**Check:** replay reconstructs a canonical event sequence, DAG hash, and merged logical state.

**Acceptance:** replay completes without invoking execution code and returns `Merged=60`.

## SCN-07-02 — Reverse physical sibling order

**Inputs:**

- Log A: `P, WA, WB, M`
- Log B: `P, WB, WA, M`

**Check:** physical arrival order differs, while causal structure is unchanged.

**Acceptance:** `canonical(A) == canonical(B)`, DAG hashes match, and both replay results contain `Merged=60`.

## SCN-07-03 — Worker execution isolation

**Setup:** the EXP-06 worker entry point is replaced by a guard that raises if called.

**Check:** replay is run against an already-recorded log.

**Acceptance:** replay succeeds and the worker guard is never triggered.

## SCN-07-04 — Fixed canonical reference

**Check:** the canonical hash for the fixture is compared against a fixed test constant derived independently from the EXP-06 canonical representation.

**Acceptance:** hash identity and `Merged=60` match the recorded reference.

## Explicit non-scenarios

The following are outside R0:

- malformed/corrupted logs;
- missing events;
- invalid parent links;
- altered logical clocks;
- arbitrary event schemas;
- distributed replay;
- mutation testing.

Those belong to later validation work, with corruption resistance reserved for EXP-08.
