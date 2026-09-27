# RUN1_RUN2_PROVENANCE_CAUSALITY_V0 — H1–H8 Evidence Matrix

Task baseline: commit `547b1fa29a725fba4f64411d7536dd60c35934dc`.

No new AnyModel requests were made.

## Decision rule

`VERIFIED` means the factual proposition is directly established by preserved evidence and independent provenance checks.

`CONTRADICTED` means preserved evidence directly conflicts with the hypothesis as stated.

`INCONCLUSIVE` means evidence is compatible with the hypothesis but does not satisfy the causal gate.

A hypothesis is not marked CONTRADICTED merely because its evidence is incomplete.

## Matrix

| Hypothesis | Evidence for | Evidence against / limitation | Status |
|---|---|---|---|
| H1 — catalog/order effect | Run 1 and Run 2 orders differ materially; Run 2 follows its catalog order 87/87; 37 divergences are distributed across changed positions | No controlled order-only comparison; adjacent models can move in different directions | INCONCLUSIVE |
| H2 — temporal/server-state effect | Runs occur at different times; 37 divergences; Run 2 divergences cluster temporally | No direct server-state observation; temporal adjacency cannot establish cause | INCONCLUSIVE |
| H3 — provider-specific transient behavior | Divergences cluster strongly by provider/model; xAI has a distinct Run1→Run2 recovery pattern | Provider identity is confounded with order/time; no provider-isolated intervention | INCONCLUSIVE |
| H4 — rate-limit/retry effect | Run 1 contains xAI 429/503 patterns; Run 2 xAI chat attempts are 200 | Run 1 rate-limit headers were not preserved; Run 2 xAI attempts preserve no retry/rate-limit headers; no direct retry event is observed | INCONCLUSIVE; specific “429/503 caused by rate limiting” claim is NOT ESTABLISHED |
| H5 — transport/network effect | Timeouts, 4xx/5xx and successful responses are directly observed | No controlled network condition; upstream/provider transport and network effects cannot be separated | INCONCLUSIVE |
| H6 — harness/environment effect | Harness source is sequential and unchanged between harness origin and Run2 artifact commit; Run2 artifact commit does not alter harness | Runtime environment, auth identity, network path and all execution-time variables are not fully preserved | INCONCLUSIVE; “harness source changed between runs” is CONTRADICTED by Git provenance |
| H7 — evidence-schema/provenance effect | Run1 artifact lacks per-attempt timestamps/headers that Run2 preserves; artifact/blob/source commits are verified | This explains an evidence limitation, not the observed availability divergence itself; missing fields cannot be reconstructed | VERIFIED as evidence limitation; NOT established as cause of divergence |
| H8 — mixed cause | Multiple mechanisms remain observationally compatible | No controlled decomposition identifies independent causal contributions | INCONCLUSIVE |

## Factual propositions that can be VERIFIED now

1. Run1 and Run2 used the same committed harness lineage; the Run2 artifact commit itself changes only the artifact.
2. The committed Run1 artifact does not preserve per-attempt timestamps or response headers.
3. The committed Run2 artifact does preserve per-attempt timestamps and response headers.
4. The two runs have 87 common models and 261 probes each.
5. 50/87 transport sequences are identical and 37/87 differ.
6. Run2 execution order equals its catalog snapshot order.
7. No preserved evidence currently satisfies the causality gate for H1–H8.

## Factual propositions that are CONTRADICTED

Only the following narrow proposition is currently contradicted:

- **“The harness source was changed between Run1 and Run2.”** — CONTRADICTED by Git provenance: the harness predates Run2, and the Run2 artifact commit adds only the Run2 artifact.

No broad causal hypothesis H1–H8 is contradicted by the current evidence.

## Important non-conclusions

- Run2 xAI HTTP 200 does not prove absence of provider-side rate limiting.
- Run1 xAI 429/503 does not prove rate limiting was the cause.
- Run2 temporal/provider clustering does not prove order caused recovery.
- Missing Run1 headers do not prove those headers were absent at runtime.
- Stable harness source does not prove identical runtime environments.

## Causality status

`CAUSALITY_NOT_ESTABLISHED`

Recommended state remains:

`INCONCLUSIVE`

The evidence currently supports several competing explanations without a controlled exposure that separates them.
