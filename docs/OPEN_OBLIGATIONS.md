# Open Obligations Registry

verified_at: 2026-11-10T06:54:49Z
rule: re-verify if older than 24h before any decision

Все записи сгруппированы по типу. `Last Evidence` указывает на
конкретный SHA, Run ID, Job ID, Artifact ID или комментарий.
Отсутствие evidence не доказывает OPEN: при отсутствии подтверждения
фактический статус должен быть `UNKNOWN`, а не назначаться по предположению.

## Backlog (не на roadmap)

| ID | Type | Status | Last Evidence | Blocking | Next Action |
|----|------|--------|---------------|----------|-------------|
| RB-001 | backlog | NOT ON ROADMAP | planning note; SWE-rebench V2.1 is external reference only | no | не начинать до условий возврата |

**RB-001 — Benchmark Task Integrity.** Методология SWE-rebench
(проверка качества benchmark-задач) потенциально применима к
контролю evaluation-наборов. Отложено; это backlog, не текущая
roadmap-задача и не подтверждённая реализация.

Условия возврата: EVERYNODE MVP закрыт, #557 закрыт, текущие
обязательные gates JAMP перепроверены. До возврата — определить
архитектурное место относительно C1–C8, PH-01..PH-06, DEC-001..012.
SWE-rebench V2.1 — внешний ориентир, не доказательство качества
JAMP benchmark-наборов.

## Architecture documents

| ID | Type | Status | Last Evidence | Blocking | Next Action |
|----|------|--------|---------------|----------|-------------|
| EN-FND-001 | doc | DRAFT-COMMITTED | merge SHA `c1e6ac4b1611596211974d78535416af307877bc` | no | внешнее ревью §18, закрытие ADR-011..015 |

**EN-FND-001 — EVERYNODE FOUNDATION v0.1.** Status: DRAFT, NOT
APPROVED, NOT IMPLEMENTED. Architecture Acceptance (§18) не
выполнена. EN-ADR-001..015 остаются `OPEN`. Наличие документа
в main не является архитектурным одобрением или доказательством
реализации.

## Pull Requests

| ID | Type | Status | Last Evidence | Blocking | Next Action |
|----|------|--------|---------------|----------|-------------|
| PR #559 | PR | MERGED | merge SHA `14e4c7dfd22ae80a1b643eb38f48c74ebb9a33c1`; post-merge CI: Pytest `42771008971` / Job `129678539478` / Artifact `13742380715`; Developer Quality `42771009044` / Job `129678539894`; G4 `42771008996` / Job `129678540099` / Artifact `13741557505`; P23.0-B `42771009431` / Job `129678545331` | no | closed |
| PR #558 | PR | MERGED | merge SHA `c1e6ac4b1611596211974d78535416af307877bc` | no | closed |
| PR #556 | PR | CLOSED / DEFERRED | comment `6747997706` | no | see #557 |

## Issues

| ID | Type | Status | Last Evidence | Blocking | Next Action |
|----|------|--------|---------------|----------|-------------|
| #557 | issue | OPEN | issue #557; state=open | no | B1–B5 (см. issue DoD) |

## Gaps

| ID | Type | Status | Last Evidence | Blocking | Next Action |
|----|------|--------|---------------|----------|-------------|
| KNOWN-GAP-G1-ALIAS | gap | OPEN | PR #559 alias Run `42753030496` / Job `129620954797`; actual G1 Run `42753030836` / Job `129620874679`; post-merge G1 Run `42771009155` / Job `129678543291` / Artifact `13741677405` | yes for trusted-lineage claim | harden PR verifier, then bind Ruleset 23974688 to `trusted-lineage` (GitHub Actions app 15368) |

**KNOWN-GAP-G1-ALIAS.**

**Confirmed alias behavior (PR #559):** Ruleset 23974688 still requires
`G1 Trusted Lineage`, but that check-run is produced by the job with the
same name inside `.github/workflows/research-loop-v0.yml`. Its complete
step is `test "success" = "success"`; it only mirrors the dependency result
of `research-loop-gate`. Evidence: PR Research Loop Run
`42753030496`, alias Job `129620954797`, Check Run
`129620954797`, head SHA
`c87af036f836fb2ffa93cd23e6a1e07d0d3753c3`. This required context is
not an independent trusted-lineage proof.

**Actual PR verifier (not currently required by Ruleset):**
`.github/workflows/g1-trusted-lineage.yml` runs on
`pull_request_target` without checking out PR code and with read-only
`actions` / `pull-requests` permissions. It validates repository/PR
identity, exact PR head SHA, and a successful Research Loop workflow run
and job. PR #559 evidence: Run `42753030836`, Job / Check Run
`129620874679`, check name `trusted-lineage`, GitHub Actions app ID
`15368`, conclusion SUCCESS.

**Semantic defects still open in the actual PR verifier:**
1. It filters for successful Research Loop runs before selecting the
   newest. A newer failed or in-progress run for the same head can be
   masked by an older successful run. Selection must identify the newest
   run first, regardless of conclusion/status, wait for that run to become
   terminal, and then require SUCCESS; otherwise fail closed.
2. It verifies the Research Loop run/job but does not download and validate
   the `research-loop-v0-evidence` artifact. The PR verifier should bind
   artifact contents to exact PR number, head SHA, run ID, expected job,
   conclusion, and Frozen Core blob; missing, expired, duplicate, malformed,
   or mismatched evidence must fail closed.
3. The workflow should emit a compact, inspectable G1 evidence artifact
   recording the exact upstream run/job/artifact and its own run/job identity.

**Post-merge verifier (separate layer):** On merge SHA
`14e4c7dfd22ae80a1b643eb38f48c74ebb9a33c1`, G1 main Run
`42771009155`, Job `129678543291`, Artifact `13741677405`
completed SUCCESS. The artifact reports
`validation_result=ALL_ASSERTIONS_PASSED` and records:
- PR #559 head `c87af036f836fb2ffa93cd23e6a1e07d0d3753c3`;
- PR Research Loop Run `42753030496`, Job `129620867966`,
  Artifact `13734506901`;
- PR alias Run `42753030496`, Job `129620954797`;
- actual PR G1 Run `42753030836`, Job `129620874679`;
- main Research Loop Run `42771008904`, Job
  `129678539358`, Artifact `13742146313`;
- Frozen Core blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

This proves the separate post-merge verifier's assertions for this merge.
It does not turn the alias into a semantic PR required-check and cannot
replace pre-merge enforcement.

**Required-check design (proposal; not yet implemented):**
- Keep `Research Loop v0 Gate /` as a required PR check.
- After hardening the actual PR verifier above, require its check-run
  `trusted-lineage` from GitHub Actions app ID `15368` in Ruleset
  `23974688`; do not substitute either `(main)` workflow.
- Update G1 main verifier to validate the same actual PR G1 check and
  retire its dependency on the alias context.
- Do not edit Ruleset 23974688 until the hardened check has terminal
  SUCCESS on a PR head and its negative/fail-closed cases are demonstrated.
- Until then, wording remains: "G1 required alias passed; separate
  post-merge G1 verifier completed successfully." Do not claim the
  required alias itself proves trusted lineage.

Current main SHA: `14e4c7dfd22ae80a1b643eb38f48c74ebb9a33c1`.
Legacy combined Commit Status API on this SHA returned
`state=pending`, `total_count=0`, `statuses=[]`; this endpoint does
not aggregate Actions Check Runs and is not a GREEN indicator.

## Stage C

| ID | Type | Status | Last Evidence | Blocking | Next Action |
|----|------|--------|---------------|----------|-------------|
| C6.2 | stage | VERIFIED | main SHA `488a02053903eeea4544524b8c97a30961a7de58`; Runs `42342882200`, `42342882225`, `42342882157`, `42342882221`, `42342882222`, `42342882201` — SUCCESS | no | closed |

C6.2 относится к merge PR #553. Это историческое evidence на SHA
`488a02053903eeea4544524b8c97a30961a7de58`, а не утверждение,
что текущий main остаётся на этом SHA.

## Legacy

| ID | Type | Status | Last Evidence | Blocking | Next Action |
|----|------|--------|---------------|----------|-------------|
| P31 | legacy | STALE / SUPERSEDED | branch `139a9658eb57097b1283f3619e8120dfbfe569a6`; current main is 694 commits ahead; branch has 0 unique commits | no | keep as reference |

## Reference branches (do not modify)

- `feat/github-oauth-dashboard` @ `0d2045e132cb2c3c18e4ed229f87e8de0239eac8` — reference for #557
- `feature/p31-telegram-transport-v1` @ `139a9658eb57097b1283f3619e8120dfbfe569a6` — superseded

## Notes

- Post-merge main SHA: `c1e6ac4b1611596211974d78535416af307877bc`.
- Run Pytest: Run `42752090142`, Job `129617825245`, SUCCESS, Artifact `13734266294`.
- Developer Quality: Run `42752090112`, Job `129617824542`, SUCCESS; no artifact.
- G4 MinIO Runtime: Run `42752090143`, Job `129617824569`, SUCCESS, Artifact `13733907774`.
- Research Loop v0 Gate (main): Run `42752090201`, Job `129617825035`, SUCCESS, Artifact `13733981668`.
- G1 Trusted Lineage (main): Run `42752090279`, Job `129617825867`, SUCCESS, Artifact `13733662333`; see KNOWN-GAP-G1-ALIAS.
- SBOM: Run `42752090212`, Job `129617825143`, SUCCESS, Artifact `13733992233`.
- `docker-smoke` in Developer Quality Job `129617826533` — SKIPPED, не PASS.
- `import-historical.yml` Run `42752088885` — known orphaned failure with `jobs=[]`; excluded from required checks, not treated as a general HOLD.
- Frozen Core `src/jamp/run.py` blob on main SHA `c1e6ac4b1611596211974d78535416af307877bc`: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`; `Δ=0`. Any change requires explicit Core Unlock.
