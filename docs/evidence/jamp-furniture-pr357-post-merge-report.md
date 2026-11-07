# JAMP Furniture — PR #357 post-merge evidence report

**State:** `CLOSED / MERGED`  
**Evidence status:** product CI `VERIFIED`; `import-historical.yml` anomaly remains `UNRESOLVED`.  
**Evidence captured:** 2026-10-13.

## 1. Merge identity

- Repository: [qwertymarketolog-lab/JAMP](https://github.com/qwertymarketolog-lab/JAMP)
- PR: [#357 — docs: add corner table specification and assets](https://github.com/qwertymarketolog-lab/JAMP/pull/357)
- Merge method: squash.
- Merge commit / main SHA: `863ce54883c5380c2bacf06fa40fa40e876a7cd9`.
- Main branch was read back at this SHA before this report was created.
- PR isolated commit before squash: `55a2e61426c59155246a330421a0f32fee6e5f75`.

## 2. Change scope

PR #357 adds exactly these three files:

| File | Blob SHA on PR diff |
|---|---|
| `corner_table_docs/jamp_corner_parts_list.mhtml` | `6400bfb2f51e4c99952243c1f456a6bb2a288472` |
| `corner_table_docs/jamp_corner_price_estimate.mhtml` | `c96b8b3eb40da1d09d0c5f41012701e4d075a69e` |
| `corner_table_docs/jamp_corner_specification.md` | `70a16f3c8eff6b4c552cecaeae3d85c2aaccc058` |

PR file-list evidence reports all three as `added`. Scope is documentation/assets only. No application code, tests, or workflow files were part of PR #357.

## 3. Post-merge CI — terminal Run → Job → artifact evidence

All three runs below target `main@863ce54883c5380c2bacf06fa40fa40e876a7cd9`.

### Pytest

- Workflow: `.github/workflows/test.yml` (Run Pytest).
- Run: [38394884434](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/38394884434).
- Run conclusion: `success`; status: `completed`.
- Job: `115287455769` (`test`), `completed / success`.
- Observed successful steps: architectural boundary validation; full test suite; generate empirical P17.6 report; upload empirical P17.6 artifact.
- Artifact: `p17-6-experiment-report`, ID `11810684590`, not expired at inspection.
- Artifact SHA-256 digest: `69e5b36cc57211b0fd86cc280448c26f997ac301dfd850d0584673a9cd25ccb2`.
- Scope: terminal CI result and artifact metadata verified. Artifact payload contents were not independently inspected as part of this report.

### Developer Quality

- Run: [38394883861](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/38394883861).
- Run conclusion: `success`; status: `completed`.
- Job: `115287454546` (`quality`), `completed / success`.
- Observed successful steps: architectural isolation tests; full test suite; Phase A runner self-tests; EXP-18 R1 and R2.1 target tests; Ruff; Mypy; Baseline integrity.
- Artifacts: none returned for this run. Successful Job evidence is available; no artifact is claimed.

## 4. Frozen Core invariant

- File: `src/jamp/run.py`.
- Expected blob SHA: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
- Blob SHA fetched at `863ce54883c5380c2bacf06fa40fa40e876a7cd9`: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
- Result: exact match; `Δ(src/jamp/run.py) = 0`.

## 5. Separate historical-workflow anomaly

- Workflow: `.github/workflows/import-historical.yml`.
- Run: [38394882098](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/38394882098).
- Target SHA: `863ce54883c5380c2bacf06fa40fa40e876a7cd9`.
- Run result: `completed / failure`.
- Jobs: `[]`; artifacts: none.
- Classification: zero-job workflow anomaly, tracked separately from the two successful product CI runs.
- Root cause: `UNRESOLVED`. The zero-job result is not described as a test failure and is not treated as a pass.

## 6. Decision

- PR #357: `MERGED`.
- Post-merge Pytest: `VERIFIED / SUCCESS`.
- Post-merge Developer Quality: `VERIFIED / SUCCESS`.
- Frozen Core: `VERIFIED / Δ=0`.
- Historical workflow anomaly: `UNKNOWN / HOLD` for root-cause classification; no product-code change is justified by the evidence recorded here.
- Overall JAMP Furniture documentation task: `CLOSED / MERGED`, with the unrelated historical-workflow anomaly preserved explicitly rather than silently cleared.

## Evidence boundaries

This report records the GitHub API observations listed above. It does not claim that the historical workflow anomaly has been fixed, that its root cause is known, or that the P17.6 artifact payload has been independently validated.
