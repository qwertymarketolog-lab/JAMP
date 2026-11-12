# E4 Known Limitations

## Historical MOEX series completeness

The MOEX ISS historical series used by E4 may contain approximately 2–3% fewer rows than a rough expected-trading-day estimate. In the Ticker Audit report, the retrieved series contained 3,364 rows against an approximate expectation of 3,458 rows (a difference of 94 rows, about 2.7%).

This aggregate gap means that completeness of the entire multi-year history is **not established**. The audit does not establish which years account for the missing rows, so the gap must not be attributed to particular years without further evidence.

### Impact on claim-specific verification

For a claim that names a particular year, E4 evaluates observations within that claimed year and includes the observed date in its evidence. The ALRS claim for 2021 was reported with:

- `claimed_year: 2021`
- `trading_days_in_claimed_year: 255`
- `observed_max_high: 153.73`
- `observed_max_high_date: 2021-09-14`

The observed high is within the stated 2% tolerance of the 153 RUB claim. The 2021 observation count is consistent with a full trading year and the dated observation supports this specific claim. This conclusion is limited to the 2021 claim; it does not certify completeness of the other years in the retrieved series.

### Verification boundary

- **Claim-specific, year-scoped verification:** may be supported when the claim year has sufficient dated observations and the relevant evidence meets the verifier's criteria.
- **General claims about the entire historical period:** remain subject to a separate, year-by-year completeness assessment.
- **Full-history completeness:** not verified by the current E4 audit.

No E4 v2 completeness project is implied by this limitation note. It is recorded as a known limitation, not a blocker for the audited ALRS 2021 claim.

## Evidence reference

- Ticker Audit workflow run: [40745058186](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/40745058186)
- Head SHA: `bad562c136697d752678725588660f19242d6e43`
- Artifact: `ticker-audit-report`, ID `12840892793`
- Artifact SHA-256: `4557c6f27d04034c2b5ee217204477a62f41c566737f5e77daf7ba0ea6a929c4`
