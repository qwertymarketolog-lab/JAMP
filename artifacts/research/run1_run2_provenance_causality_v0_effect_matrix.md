# RUN1_RUN2_PROVENANCE_CAUSALITY_V0 — Quantitative H1–H5 Effect Matrix

Read-only analysis of existing Run1/Run2 artifacts. No new AnyModel requests.

## Baseline

- Models: 87
- Probes/run: 261
- Sequence differences: 37/87 (42.5%)
- Run1 non-200 observations: 106/261 (40.6%)
- Run2 non-200 observations: 51/261 (19.5%)
- Net reduction: 55 failed/non-200 observations

## Provider × divergence matrix

| Provider | Models | Differing models | Difference rate | Run1 non-200 | Run2 non-200 |
|---|---:|---:|---:|---:|---:|
| ag | 15 | 7 | 46.7% | 9 | 7 |
| am | 15 | 7 | 46.7% | 17 | 8 |
| cc | 11 | 1 | 9.1% | 12 | 9 |
| cx | 15 | 7 | 46.7% | 12 | 0 |
| ds | 2 | 0 | 0% | 0 | 0 |
| flow | 3 | 0 | 0% | 9 | 9 |
| gcli | 1 | 1 | 100% | 1 | 0 |
| glm | 7 | 1 | 14.3% | 0 | 3 |
| kmc | 2 | 2 | 100% | 6 | 0 |
| qwen | 3 | 1 | 33.3% | 1 | 0 |
| xai | 10 | 10 | 100% | 30 | 6 |

The xAI signal is unusually concentrated: 10/10 xAI models differ; the two image models remain 400×3 while the eight chat models move from Run1 503/429 patterns to Run2 200×3.

## Run2 position × divergence

| Run2 positions | Models | Differing | Difference rate | Recoveries | Regressions |
|---|---:|---:|---:|---:|---:|
| 1–20 | 20 | 8 | 40% | 5 | 2 |
| 21–40 | 20 | 9 | 45% | 8 | 0 |
| 41–60 | 20 | 16 | 80% | 14 | 0 |
| 61–80 | 20 | 3 | 15% | 2 | 1 |
| 81–87 | 7 | 1 | 14.3% | 1 | 0 |

The 41–60 block is the strongest positional concentration: 16/20 differences and 14/20 recoveries.

However, this block also contains the entire xAI cluster and other provider/model clusters. Therefore position, provider and time are confounded.

## Status transition matrix — dominant patterns

| Run1 sequence → Run2 sequence | Models |
|---|---:|
| 200,200,200 → 200,200,200 | 40 |
| 503,429,429 → 200,200,200 | 8 |
| 404,404,404 → 404,404,404 | 7 |
| 200,503,200 → 200,200,200 | 4 |
| 200,timeout,200 → 200,200,200 | 3 |
| 503,503,503 → 503,503,503 | 3 |
| 200,200,503 → 200,200,200 | 2 |
| 502,502,502 → 200,200,200 | 2 |
| 503,429,429 → 400,400,400 | 2 |

The eight xAI chat recoveries account for the entire `503,429,429 → 200,200,200` pattern.

## H1 — Catalog/order effect

**Evidence supporting:** strong position concentration exists: 80% divergence in Run2 positions 41–60 versus 14–15% in positions 61–87.

**Narrow prediction contradicted:** a simple monotonic “later position ⇒ worse/better outcome” explanation is contradicted. The 61–80 and 81–87 blocks have much lower divergence than 41–60, despite occurring later.

**Causal status:** INCONCLUSIVE. Position remains a plausible exposure, but provider and time are confounded.

## H2 — Temporal/server-state effect

**Evidence supporting:** the strongest divergence block occurs in the middle of the Run2 timeline; 16/20 positions 41–60 differ.

**Narrow prediction contradicted:** no simple monotonic time trend is present. Divergence drops sharply after the 41–60 block.

**Causal status:** INCONCLUSIVE. No direct server-state variable was preserved.

## H3 — Provider-specific transient behavior

**Evidence supporting:** xAI 10/10 models differ; xAI has 30 Run1 non-200 vs 6 Run2 non-200. cx has 7/15 differences and 12→0 non-200; kmc has 2/2 and 6→0.

**Narrow prediction contradicted:** none. Provider-specific effects remain compatible with the data.

**Important confound:** provider blocks overlap with Run2 positions and time.

**Causal status:** INCONCLUSIVE.

## H4 — Rate-limit/retry effect

**Evidence supporting:** the xAI chat transition `503,429,429 → 200,200,200` occurs for 8 models, a highly specific repeated transport pattern.

**Narrow prediction contradicted:** the stronger claim “all xAI Run1 failures were rate-limit driven” is NOT established and should not be asserted. Run1 headers were not preserved; Run2 has no preserved retry/rate-limit headers for these successful xAI chat attempts.

**Causal status:** INCONCLUSIVE.

The 429 observations are real; their causal interpretation is not.

## H5 — Transport/network effect

**Evidence supporting:** Run1 has 106 non-200 observations versus 51 in Run2; transitions include 503/429, 502 and timeout → 200.

**Narrow prediction contradicted:** a pure generic-network explanation does not account for the structured provider/model pattern by itself; stable 404 groups remain 404×3 in both runs and xAI image models remain 400×3 while xAI chat models recover.

This does NOT contradict transport involvement; it contradicts treating “network instability” as a sufficient single explanation.

**Causal status:** INCONCLUSIVE.

## Causal conclusion

No broad H1–H5 hypothesis is currently CONTRADICTED.

Three narrower predictions are contradicted:

1. Simple monotonic position effect.
2. Simple monotonic temporal effect.
3. “Generic transport/network instability alone explains the divergence.”

H3 remains fully compatible with the observed provider concentration, while H4 has a strong descriptive signal but lacks the historical headers required for causal attribution.

**CAUSALITY_NOT_ESTABLISHED**

**STATE: INCONCLUSIVE**
