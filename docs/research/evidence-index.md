# Canonical evidence index

This index is the publication surface for closed research evidence chains under the **any-ref-with-index** rule defined in `docs/research/evidence-publication-rule.md`.

A chain is canonically published only when this index names its exact ref and evidence path. Branch existence alone is insufficient.

## EXP-02

- Ref: `exp-03-spec`
- Evidence: `docs/research/exp-02-transfer.md`
- Evidence blob: `15df3fba6902678fc92df6a946c9dc6bb9e8ac6d`
- Recorded result: `PARTIAL TRANSFER`
- Repository link: https://github.com/qwertymarketolog-lab/JAMP/blob/exp-03-spec/docs/research/exp-02-transfer.md

## EXP-03

- Ref: `exp-03-spec`
- Specification: `docs/research/EXP-03-SEARCH-TRANSFER.md`
- Specification blob: `9c8fd044a0b7fa0f328d1cdeb8067f9542d34a25`
- Evidence: `docs/research/EXP-03-EVIDENCE.md`
- Evidence blob: `2e674d02db7981cf5ef6b81d69171120f3eaf8c6`
- Recorded outcome: `B — TARGET PASS`
- Specification link: https://github.com/qwertymarketolog-lab/JAMP/blob/exp-03-spec/docs/research/EXP-03-SEARCH-TRANSFER.md
- Evidence link: https://github.com/qwertymarketolog-lab/JAMP/blob/exp-03-spec/docs/research/EXP-03-EVIDENCE.md

## Q3b

- Ref: `q3b-closed-evidence`
- Evidence: `docs/research/q3b-artifact-contract.md`
- Evidence blob: `249a28bd7bd045b6fc60f48398e6a69ff2431c72`
- Closure commit: `80335f5b3ec29bae4998d184caeff02c7d5202a9`
- Recorded status: `Q3b CLOSED` (Q3b.1 SPECIFIED; Q3b.2 PASS; Q3b.3 PASS)
- Repository link: https://github.com/qwertymarketolog-lab/JAMP/blob/q3b-closed-evidence/docs/research/q3b-artifact-contract.md

## EXP-04

- Ref: `feature/exp-04-4queens`
- Evidence: `docs/research/EXP-04-EVIDENCE.md`
- Evidence blob: `8ea4ce018edd14d854b706a3518b4006df50e4a3`
- Execution commit: `0b12d63a49cab7fbb804f9fad29a3dbaa68ccb3d`
- Run Core blob at execution: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Adapter blob: `f0f210359297abc0e327921599a6b3ff01b08af1`
- Test blob: `74d2249835bf13a78d2ed90d73c539c5de1cf244`
- Workflow blob: `251d1d5f4f93593e784f80dea19f0ea435ca9a3f`
- CI run: `35016967681`
- Execution artifact: `10416510391`
- Artifact SHA-256: `3d51ded65b0f5ec6b8f0db057070b903fdee102368c7ac833f7a2fc21d0ce0f5`
- Recorded outcome: `TARGET PASS`
- Scope note: `Artifact v0 envelope neutrality was not tested by EXP-04`
- B-audit: `docs/research/EXP-04-B-AUDIT.md`
- B-audit result: `PASS — RECONSTRUCTIBLE`
- Evidence link: https://github.com/qwertymarketolog-lab/JAMP/blob/feature/exp-04-4queens/docs/research/EXP-04-EVIDENCE.md
- B-audit link: https://github.com/qwertymarketolog-lab/JAMP/blob/main/docs/research/EXP-04-B-AUDIT.md

## EXP-05

- Ref: `feature/exp-05-stochastic-gridworld`
- Specification: `docs/research/EXP-05-SPEC.md`
- Scenarios: `docs/research/EXP-05-SCENARIOS.md`
- Evidence: `docs/research/EXP-05-EVIDENCE.md`
- Evidence blob: `a187e32111fe210ecf1c76e49530cb04c97a3dc9`
- Execution commit: `df93172980c365eea9b370cf06a1de5bfbd36694`
- Run Core blob at execution: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Adapter blob: `907ecd9f257b338bf0dd1413edafefc3129ec960`
- Test blob: `a6e18f6b2774981bd535a1cc3c68501af6e3aec7`
- Workflow blob: `4547902d5f7ead17215dc27af52af20fe210b5aa`
- Dedicated CI run: `35020257179`
- Recorded outcome: `TARGET PASS`
- Observation: Seed 1 and Seed 2 produced different trajectories; cross-seed divergence was not a pass/fail criterion.
- Scope note: The result is bounded to stochastic Gridworld agent/environment interaction and does not establish universal stochastic or universal problem-solving support.
- B-audit: `docs/research/EXP-05-B-AUDIT.md`
- B-audit result: `PASS — RECONSTRUCTIBLE`
- Evidence link: https://github.com/qwertymarketolog-lab/JAMP/blob/feature/exp-05-stochastic-gridworld/docs/research/EXP-05-EVIDENCE.md
- B-audit link: https://github.com/qwertymarketolog-lab/JAMP/blob/main/docs/research/EXP-05-B-AUDIT.md

## EXP-06

- Ref: `feature/exp-06-parallel-frontier`
- Specification: `docs/research/EXP-06-SPEC.md`
- Specification blob: `7c77c8766b87eec2182c3f36bd61903a1d6d4040`
- Scenarios: `docs/research/EXP-06-SCENARIOS.md`
- Scenarios blob: `be846f30bea07c943c34288c7ef63f049301d61e`
- Evidence: `docs/research/EXP-06-EVIDENCE.md`
- Evidence blob: `24c706e93b16cd77afe70e18aa15c9d9593b0e65`
- Execution / correction commits: `d5920ecd9edffbe9a56392e43bc343398aaface7`, `d2b680d38ffa420dcfd6b7449e8f5c7b7d95328d`, `62eadcc94c4df606489e8f6848098de50d77bb80`
- Run Core blob at execution: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Adapter blob: `4654c19abe7038830b109531de7105f65defb06e`
- Test blob: `c910c9952149b241ba2124bf5e4627fb5c703f18`
- Workflow blob: `58952e03aee85a650425ee11a47dd08ab1c4a9db`
- Local result: `4/4 PASS` (`4 passed in 0.77s`)
- CI visual evidence: GitHub Mobile screenshot supplied in the research session at `2026-09-15T22:38:56Z`; Run #6 failed on the pre-correction signature mismatch, Runs #7 and #8 are shown as `Success` after correction/registration. Numeric IDs for #7/#8 are intentionally not asserted because they were not captured.
- Dedicated workflow registered on `main`: commit `9e5cc16abba46f831b6131220432f98f5c1347b4`
- Recorded outcome: `CLOSED — TARGET PASS`
- Scope note: bounded to real threaded parallel-frontier execution, causal DAG canonicalization, logical replay, and Core immutability; does not establish universal concurrency or distributed-system support.
- B-audit: `docs/research/EXP-06-B-AUDIT.md`
- B-audit result: `PASS — RECONSTRUCTIBLE`
- Evidence link: https://github.com/qwertymarketolog-lab/JAMP/blob/feature/exp-06-parallel-frontier/docs/research/EXP-06-EVIDENCE.md
- B-audit link: https://github.com/qwertymarketolog-lab/JAMP/blob/main/docs/research/EXP-06-B-AUDIT.md
