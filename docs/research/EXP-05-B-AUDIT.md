# EXP-05 — B-Audit

## Canonical reconstruction path

`main` → `docs/research/evidence-index.md` → `feature/exp-05-stochastic-gridworld` → `docs/research/EXP-05-EVIDENCE.md`

Evidence blob named by the index: `a187e32111fe210ecf1c76e49530cb04c97a3dc9`.

## 1. Claim

**PASS.** The evidence states the bounded claim precisely: the frozen stochastic agent/environment forcing case is representable by the Run Core without modifying `src/jamp/run.py`. It explicitly excludes universal stochastic or universal problem-solving claims.

## 2. Anchor

**PASS.** The evidence identifies the frozen Run Core blob as `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`, the exact experiment ref, the execution commit `df93172980c365eea9b370cf06a1de5bfbd36694`, and the dedicated workflow run `35020257179`. The workflow independently checked the Core blob SHA-1 before executing the EXP-05 tests.

## 3. Code

**PASS.** The evidence records exact blobs for the adapter (`907ecd9f257b338bf0dd1413edafefc3129ec960`), test (`a6e18f6b2774981bd535a1cc3c68501af6e3aec7`), and workflow (`4547902d5f7ead17215dc27af52af20fe210b5aa`). The evidence also states that `src/jamp/run.py` was not modified.

## 4. Test

**PASS.** Dedicated workflow `35020257179` checked the frozen Core blob and ran `tests/research/test_exp05_stochastic_gridworld.py`. The recorded CI output is `4 passed in 0.04s`.

The four tests cover Core immutability, EXP-05A stochastic deviation and atomicity, EXP-05B replay determinism for both seeds, and explicit agent/environment provenance.

## 5. Result

**PASS.** The evidence records six steps and six events for the tested seeds; seed 1 contains an observable intended-vs-actual deviation, seed 2 is replay-deterministic, and each event carries before/after state snapshots plus explicit source attribution. Cross-seed trajectory divergence is recorded as observation only, matching the frozen protocol.

## 6. Outcome

**PASS.** An independent reader can reconstruct the evidence chain from the canonical index through the exact branch/ref and evidence path, then follow the recorded execution commit, code blobs, workflow run, and observed result. The dedicated EXP-05 run is sufficient to reconstruct the stated bounded outcome.

## Final verdict

**PASS — RECONSTRUCTIBLE**
