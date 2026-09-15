# EXP-06 B-AUDIT — Provenance and Reconstruction Audit

**Audit status:** PASS — RECONSTRUCTIBLE  
**Experiment:** EXP-06 Parallel Frontier & Asynchronous Completion Boundary  
**Canonical evidence ref:** `feature/exp-06-parallel-frontier`  
**Evidence:** `docs/research/EXP-06-EVIDENCE.md`  
**Evidence blob:** `24c706e93b16cd77afe70e18aa15c9d9593b0e65`

## B-audit questions

### 1. Claim

**PASS.** The claim is explicit in the frozen specification: determine whether unchanged Run Core v0.3 can contain real concurrent parallel-frontier computation externally while preserving causal provenance and auditable logical replay.

Specification blob: `7c77c8766b87eec2182c3f36bd61903a1d6d4040`.

### 2. Anchor

**PASS.** The frozen Core anchor is exact Git blob SHA-1 `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`. `main/src/jamp/run.py` currently has exactly this blob SHA-1.

### 3. Code

**PASS.** The adapter and test code are identified by exact commits and blob SHAs in the evidence record:

- adapter commit `d5920ecd9edffbe9a56392e43bc343398aaface7`; blob `4654c19abe7038830b109531de7105f65defb06e`;
- test commit `d2b680d38ffa420dcfd6b7449e8f5c7b7d95328d`; blob `c910c9952149b241ba2124bf5e4627fb5c703f18`;
- workflow blob `58952e03aee85a650425ee11a47dd08ab1c4a9db`.

### 4. Test

**PASS.** The four frozen scenarios are directly represented in the dedicated test file: Core immutability, execution-span overlap, anti-fake concurrency, and canonical lineage replay. The corrected local execution recorded `4 passed in 0.77s`.

### 5. Result

**PASS.** The evidence record gives the bounded result for all four scenarios and preserves the important boundary: physical completion order may differ, while canonical causal representation and logical merged state remain invariant.

### 6. Outcome

**PASS.** The recorded scientific outcome is `CLOSED — TARGET PASS`, explicitly bounded to the EXP-06 protocol and not generalized to universal concurrency, distributed systems, or every problem class.

## CI provenance note

The research session also supplied a GitHub Mobile screenshot dated `2026-09-15T22:38:56Z` showing EXP-06 Run #6 failure followed by Run #7 and Run #8 success. The repository does not contain the numeric IDs of Runs #7/#8, so this audit does not invent them or claim log-level details that were not captured. The CI screenshot is supplementary confirmation; reconstruction of the protocol result does not depend on it because the exact specification, Core anchor, adapter/test blobs, and local 4/4 execution are independently recorded.

## Core purity conclusion

No EXP-06 correction modified `src/jamp/run.py`. The adapter was brought into conformance with the existing one-argument `run()` contract instead. The current `main` Core blob remains `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

**Final B-audit verdict: PASS — RECONSTRUCTIBLE.**
