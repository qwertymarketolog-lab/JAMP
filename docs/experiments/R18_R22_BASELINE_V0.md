# R18–R22 Pipeline — Baseline v0

**Status:** FROZEN EVIDENCE
**Date:** 2026-10-28
**Stage:** R18–R22 v0 (claim extraction → citation check → E4 verification → coverage)

## Evidence

- **Run ID:** 40639519422
- **Job ID:** 122654141157
- **SHA:** b4d8bb47e9c553414320989b65ff859d9600c8a5
- **Artifact ID:** 12794823201
- **Artifact SHA-256:** 11ab0cda8382d8f61585eabfcc416b871803d5bc0cf40f84aaada0470816d253

## Coverage (semantic definition)

| Metric | Value | Definition |
|---|---|---|
| total | 4 | all extracted claims |
| supported | 0 | proven true by source |
| contradicted | 0 | proven false by source |
| not_found | 1 | source confirms absence (verified, not confirmed) |
| ambiguous | 0 | source out-of-scope for claim type |
| inconclusive | 3 | verification requires E5 or historical data |
| verified | 1 | supported + contradicted + not_found |
| confirmed | 0 | supported + contradicted |
| verified_ratio | 0.25 | verified / total |
| confirmed_ratio | 0.0 | confirmed / total |

**Key invariant:** `confirmed_ratio = 0.0` means **no claim was proven true or false** in this run. `verified_ratio = 0.25` means for one claim (FakeTech) the source returned a conclusive answer — "not in MOEX catalog" — which is a fact about the source, not about the company's existence.

## Claims

| ID | Claim | Type | Verdict | Reason |
|---|---|---|---|---|
| claim-0001 | SBER достиг 5000 ₽ | historical_price | inconclusive | requires_historical_data_or_E5 |
| claim-0002 | VKCO потерял 93% капитализации | change_percent | inconclusive | requires_E5_or_history |
| claim-0003 | FakeTech объявила IPO | existence | not_found | Ticker not in MOEX catalog; scope of source |
| claim-0004 | SBER вырастет из-за дивидендов | prediction | inconclusive | requires_E5_search |

## What this baseline proves

1. R18 works: 4 claims extracted deterministically from 4 sentences.
2. R19/R21 work for the subset of claims E4 can verify (MOEX/CoinGecko existence + current price).
3. R20 works: citation URL is extracted and checked (MOEX URL reached).
4. R22 works partially: FakeTech → `not_found` via E4 existence; adversarial claim is not masked as `verified`.
5. Coverage computed and semantically explicit via `definition` field.

## What this baseline does NOT prove

1. **Historical prices** (SBER достиг 5000₽) — requires MOEX `/iss/history/` endpoint or E5.
2. **Percentage changes** (VKCO −93%) — requires historical series; E4 v0 only returns current price.
3. **Predictions and causal claims** (SBER вырастет из-за дивидендов) — require E5 (search/analysis).
4. **Non-MOEX, non-CoinGecko entities** — E4 v0 is scoped to two sources.
5. **`not_found` ≠ non-existence** — FakeTech is not in MOEX, but this does not prove the company does not exist in other jurisdictions.

**Fragility notice:** This baseline depends on MOEX API state at run time. If SBER, VKCO, or any referenced ticker is delisted, renamed, or reassigned on MOEX, re-running the E2E on the same commit SHA will produce different report.json. The baseline is a snapshot, not a permanent invariant. Ticker reassignment (same symbol, different entity) is a known semantic risk that R18–R22 v0 cannot detect; mitigation requires issue_date validation in future MOEX history adapter.

## Constraints (not to be changed without new evidence)

- `src/jamp/run.py` — Frozen Core, Δ = 0
- Thresholds: `5%` (equity), `10%` (crypto price), `20%` (crypto market cap)
- Sample in `main()` of `run_pipeline.py` — 4 claims, do not modify to inflate coverage
- Acceptance logic in `stock_audit_acceptance.py` — no changes

## Next steps (planned, not executed)

| Stage | What | Closes |
|---|---|---|
| R18–R22 v0.1 | MOEX `/iss/history/` adapter | claim-0001 (historical price) |
| R18–R22 v0.2 | E5 (Tavily/SerpAPI) | claim-0002, claim-0004 |
| R18–R22 v0.3 | Causal claim analysis | claim-0004 (partially) |

## Reproduction

Run manually via GitHub Actions → `R18-R22 Pipeline E2E` → `workflow_dispatch` → `main`. Artifact name: `r18-r22-report`. Expected output matches this document within data-variance tolerance (MOEX current price changes; verdicts for inconclusive claims are deterministic).
