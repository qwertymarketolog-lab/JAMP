# RUN1_RUN2_PROVENANCE_CAUSALITY_V0 — First Evidence Report

## Execution boundary

- Task contract commit: `3e397849694692a90e82448639709a909a6205e5`
- No new AnyModel requests were issued.
- Evidence source: existing Git artifacts, harness source/history, comparator output, and GitHub provenance.
- Frozen Core: `src/jamp/run.py` — required locked blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

## State

`INCONCLUSIVE`

Causal status: `CAUSALITY_NOT_ESTABLISHED`

The divergence itself is verified; a single causal explanation is not.

## VERIFIED

### Input provenance

- Run 1 artifact blob: `13bcc9407e7a77d09ea0f2f631d903ba8dcfaae2`
- Run 1 source commit: `69163272b7079d7883997b687c202647640b425d`
- Run 2 artifact blob: `ca231bdadcdafa302dcda131d19244f30bdf3066`
- Run 2 source commit: `36c6f23da600b37d45718530cfa693a69f498bfc`
- Harness origin: `3e105b17656018e37eb748dca73129c231b3de46`
- Run 2 artifact commit adds the artifact only; it does not modify the harness.
- Run 1 artifact was added later by commit `69163272...`; its Git blob identity is independently verified.

### Divergence

- Run 1: 87 models × 3 attempts = 261 probes.
- Run 2: 87 models × 3 attempts = 261 probes.
- Common models: 87/87.
- Identical transport sequences: 50/87.
- Different sequences: 37/87.
- Among the 37 differences:
  - 30 have increased count of HTTP 200 in Run 2;
  - 3 have decreased count of HTTP 200;
  - 4 have unchanged HTTP-200 count but different non-200 composition.
- 37/37 differences also changed the per-run status counter; 0/37 are order-only differences.

### Execution/order

- Run 2 probe order equals its catalog snapshot order: 87/87 positions, 0 inversions.
- The xAI cluster is concentrated in Run 2 positions 50–59.
- Run 2 xAI evidence: 8 chat models × 3 = 24 HTTP 200; 2 image models × 3 = 6 HTTP 400.
- Run 2 preserved per-attempt timestamps and response headers.
- Run 1 preserved no per-attempt timestamps or response headers in the committed artifact.

### Harness

The harness is sequential: model order from the catalog, then three attempts per model; no concurrency and no sleep. The harness source predates Run 2 and the Run 2 commit does not change it.

## OBSERVED

### Temporal distribution of the 37 divergences

Using Run 2 timestamps:

- 22:05–22:09: 4 differences
- 22:10–22:14: 9 differences
- 22:15–22:19: 17 differences
- 22:20–22:23: 2 differences

The xAI cluster occurred around 22:17–22:18 UTC.

### xAI headers

For the preserved Run 2 xAI evidence:

- 24 chat attempts: HTTP 200, `cf-ray` present on all.
- 6 image attempts: HTTP 400, `cf-ray` and `x-request-id` present.
- No preserved `retry-after`, `x-ratelimit-*`, or `x-should-retry` values in those xAI attempts.
- All observed xAI `cf-ray` values ended in `-EWR`.

## INFERRED

- Run order changed materially between the two runs and is a plausible exposure difference for H1.
- The large Run 2 recovery cluster is temporally/provider clustered.
- These patterns are compatible with upstream transient behavior, ordering effects, or mixed causes.
- Compatibility is not causal proof.

## HYPOTHESIS STATUS

| Hypothesis | Status | Evidence |
|---|---|---|
| H1 catalog/order effect | INCONCLUSIVE | Order differs materially; temporal/provider clustering exists; no controlled order-only experiment |
| H2 temporal/server-state effect | INCONCLUSIVE | Runs occur at different times; outcomes differ; no direct server-state evidence |
| H3 provider-specific transient behavior | INCONCLUSIVE | Strong provider/model clustering; no controlled provider-isolated intervention |
| H4 rate-limit/retry effect | INCONCLUSIVE | Run 1 has 429/503 patterns for xAI; Run 2 lacks preserved retry/rate-limit headers; Run 1 headers unavailable |
| H5 transport/network effect | INCONCLUSIVE | Timeouts/4xx/5xx are observed; no controlled network intervention |
| H6 harness/environment effect | INCONCLUSIVE | Source contract is stable across harness history; runtime environment identity is incomplete |
| H7 evidence-schema/provenance effect | VERIFIED as an evidence limitation | Run 1 artifact lacks fields preserved by Run 2; runtime receipt of missing Run 1 headers is not proven |
| H8 mixed cause | INCONCLUSIVE | Multiple compatible mechanisms remain |

## Contradictions / limits

1. A simple monotonic timeline explanation is not established: `ag/gemini-3.6-flash-low` regressed while adjacent related models recovered.
2. Run 1 cannot support historical header-level causal analysis because those headers were not preserved.
3. Run 2 header absence for a field is evidence about the preserved response, not proof that an upstream system never emitted that field.
4. Code inspection verifies the intended harness contract, not every runtime/environment value used in Run 1.

## Causality gate

No hypothesis currently satisfies all required causal-gate conditions.

Therefore:

`CAUSALITY_NOT_ESTABLISHED`

This is not evidence that the hypotheses are false.

## Scope

This report is limited to the existing Run 1/Run 2 evidence. It does not include new AnyModel probes and does not reconstruct missing historical evidence.

## Next evidence required

To establish causality rather than correlation, the next experiment must independently control at least one candidate exposure (for example execution order or a provider-isolated condition), preserve identical per-attempt timestamps and headers in both arms, and compare the resulting outcomes under the same frozen contract.

