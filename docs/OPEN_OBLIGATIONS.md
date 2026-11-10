# Open Obligations Registry

verified_at: 2026-11-10T03:56:25Z
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
| PR #558 | PR | MERGED | merge SHA `c1e6ac4b1611596211974d78535416af307877bc` | no | closed |
| PR #556 | PR | CLOSED / DEFERRED | comment `6747997706` | no | see #557 |

## Issues

| ID | Type | Status | Last Evidence | Blocking | Next Action |
|----|------|--------|---------------|----------|-------------|
| #557 | issue | OPEN | issue #557; state=open | no | B1–B5 (см. issue DoD) |

## Gaps

| ID | Type | Status | Last Evidence | Blocking | Next Action |
|----|------|--------|---------------|----------|-------------|
| KNOWN-GAP-G1-ALIAS | gap | OPEN | PR alias job `129356187670`; main verifier Run `42752090279` / Job `129617825867` / Artifact `13733662333` | no | привязать required-check к фактическому trusted-lineage результату и проверить его семантический контракт |

**KNOWN-GAP-G1-ALIAS.** В PR #558 required-check job
`129356187670` выполнял только alias-команду
`test "success" = "success"`. Поэтому сам required-check
не является самостоятельным доказательством trusted lineage.

Отдельно: post-merge G1 main Job `129617825867` не является
alias-only job. Его лог показывает проверку merge ancestry,
ассоциации ровно одного merged PR, терминального PR Research Loop
run/job/artifact, фактического PR `trusted-lineage` run/job,
а также main Research Loop run/job/artifact. Evidence artifact:
`13733662333`.

Это дополнительная проверка цепочки, но gap в самом PR required-check
остаётся: до изменения Ruleset 23974688 и проверки контракта
не заявлять, что alias required-check сам по себе доказывает
trusted lineage. Формулировка: "G1 required-check passed; separate
post-merge G1 verifier completed successfully."

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
