# R18–R22 Pipeline — Baseline v0.1 (Post-Pagination)

**Status:** FROZEN EVIDENCE
**Supersedes:** v0 (kept immutable in history — pagination was incomplete)
**Date:** 2026-10-28
**Change from v0:** MOEX history pagination fixed; claim-0001 now uses full 13-year dataset

## Evidence

- Run ID: 40649309846
- Job ID: 122685394517
- SHA: 7e3b2f68bb19c633fc1c6bb51d534afd8594b9e4
- Artifact ID: 12799430953

## Claims

| ID | Claim | Type | Verdict | Reason |
|---|---|---|---|---|
| claim-0001 | SBER достиг 5000₽ | historical_price | **contradicted** | historical_max_below_claimed (max HIGH = 388.11 over 3436 trading days / 35 pages / 2013-01-01..2026-10-28) |
| claim-0002 | VKCO потерял 93% | change_percent | inconclusive | requires_E5_or_history |
| claim-0003 | FakeTech IPO | existence | not_found | ticker not in MOEX catalog |
| claim-0004 | SBER вырастет | prediction | inconclusive | requires_E5_search |

## Coverage

- total=4
- verified=2
- confirmed=1
- verified_ratio=0.5
- confirmed_ratio=0.25

## What v0.1 proves (new)

- R22 works on a realistic hallucination: "SBER достиг 5000₽" was contradicted using the full returned historical dataset.
- MOEX history adapter fetched 35 pages and returned 3436 trading-day rows (3458 expected; approximately 99.4% coverage).
- Fail-Closed is preserved for prediction/causal claims: they remain inconclusive rather than fabricated as supported or contradicted.

## What v0.1 does NOT prove

- Historical prices for delisted/reassigned tickers (an issue-date check exists, but was not E2E-tested).
- Change-percent, prediction, or causal claims (require E5/history evidence).
- Claims about non-MOEX/CoinGecko sources.

## Fragility notice

This baseline depends on MOEX API state at run time. Ticker reassignment risk is mitigated by an ISSUEDATE check, but that check was not E2E-tested. The observed maximum is bounded by the returned source, date range, and HIGH field; it is not a universal statement about every possible SBER instrument or data source.

## Reproduction evidence

- Workflow: R18-R22 Pipeline E2E
- Run: [40649309846](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/40649309846)
- Job: [122685394517](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/40649309846/job/122685394517)
- Artifact: [r18-r22-report](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/40649309846/artifacts/12799430953)
