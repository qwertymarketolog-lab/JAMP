# EXP-06 Evidence — Parallel Frontier & Asynchronous Completion Boundary

**Status:** CLOSED — TARGET PASS  
**Specification:** `docs/research/EXP-06-SPEC.md`  
**Scenarios:** `docs/research/EXP-06-SCENARIOS.md`  
**Frozen Core blob SHA-1:** `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

## 1. Implementation provenance

- Authentic Run Core was restored on `main` at commit `9379981f12ac3f43d70459170b6408b167705ef8`.
- EXP-06 branch was rebased-equivalently on that mainline and contains only the intended experiment changes plus the workflow registration/trigger correction.
- Adapter correction commit: `d5920ecd9edffbe9a56392e43bc343398aaface7` (`EXP-06: align adapter with frozen Run API`).
- Test contract correction commit: `d2b680d38ffa420dcfd6b7449e8f5c7b7d95328d` (`EXP-06: use frozen Run single-argument contract`).
- Workflow trigger correction commit: `62eadcc94c4df606489e8f6848098de50d77bb80` (`ci(exp-06): enable workflow_dispatch for manual trigger`).
- Adapter blob SHA-1: `4654c19abe7038830b109531de7105f65defb06e`.
- Test blob SHA-1: `c910c9952149b241ba2124bf5e4627fb5c703f18`.
- Workflow blob SHA-1: `58952e03aee85a650425ee11a47dd08ab1c4a9db`.

## 2. Protocol result

### SCN-06-01 — concurrency execution span overlap

**PASS.** The adapter uses `ThreadPoolExecutor(max_workers=2)` and records real worker execution spans. The test asserts a positive overlap between WA and WB spans.

### SCN-06-02 — anti-fake concurrency guard

**PASS.** The adapter submits both workers to the executor rather than iterating them through a sequential `for w in workers: w.run()` pattern. The test also requires total worker elapsed time to be less than the sum of the two configured delays.

### SCN-06-03 — canonical lineage replay

**PASS.** Two runs deliberately reverse physical completion order. Raw completion order differs, while both worker completion events retain logical clock 2, the join retains clock 3, canonicalization produces the same event sequence, the canonical DAG hashes match, and the merged logical state is `Merged=60`.

### SCN-06-04 — Core immutability gate

**PASS.** The test computes the Git blob SHA-1 of `src/jamp/run.py` and requires `0fee0e1c5c1a1548361965ac51eacdeba62bfe8`. The current `main` file has exactly that blob SHA-1.

## 3. Local execution evidence

The corrected EXP-06 test suite was executed locally with Python 3.14.6 / pytest 8.4.2 under Termux using the stdlib runtime plus pytest dependencies required for the test. Result:

```text
4 passed in 0.77s
```

The four tests were SCN-06-04, SCN-06-01, SCN-06-02, and SCN-06-03; all passed.

The failed attempt to install the complete developer extra on Termux was environment-specific: `ruff` attempted a Rust build unsupported by the Android target. This did not prevent execution of the EXP-06 test file itself and is not treated as an EXP-06 protocol failure.

## 4. CI evidence

The GitHub Mobile screenshot supplied in the research session at `2026-09-15T22:38:56Z` records the EXP-06 workflow history:

- **Run #6 — Failure:** `EXP-06: align adapter with frozen Run API`. This is the pre-correction run and records the original two-argument `run()` contract mismatch (`TypeError`).
- **Run #7 — Success:** `EXP-06: use frozen Run single-argument contract`. This is the test-side correction run.
- **Run #8 — Success:** `ci(exp-06): enable workflow_dispatch for manual trigger`. This is the workflow-registration/trigger correction run.

The screenshot is retained here as user-supplied visual evidence. The exact GitHub numeric run IDs for Runs #7/#8 were not captured in the repository record, so they are not invented here. Accordingly, this evidence record does **not** claim log-level details for those successful runs beyond the success state visible in the supplied screenshot.

The dedicated workflow is now registered on `main` as `.github/workflows/exp-06-dedicated.yml`; its workflow blob is `58952e03aee85a650425ee11a47dd08ab1c4a9db` and the registration commit on `main` is `9e5cc16abba46f831b6131220432f98f5c1347b4`.

## 5. Scientific conclusion

**TARGET PASS — CLOSED.**

Within the frozen protocol scope, unchanged Run Core v0.3 can contain a real concurrent parallel-frontier computation in an external adapter while preserving causal provenance and logical replay. No Core-level async/event-loop/channel primitive was required.

This result is bounded to the EXP-06 protocol. It does **not** establish universal concurrency support for every scheduler, multiprocessing model, distributed system, or problem class.

## 6. Negative / boundary result

The original adapter/test invocation using `run(adapter, state)` was rejected by the unchanged Core signature. This is treated as a useful contract-boundary observation, not as a scientific forcing failure: the adapter was corrected to the frozen single-argument Run API without modifying Core.
