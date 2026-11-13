# JAMP — Input Pack для независимого аудита

## Оговорка об аудите (обязательно прочитать до всего остального)

Этот документ — подготовленная сводка фактов и ссылок на первичные артефакты, а не замена самим артефактам. Модели-аудиторы получают только этот файл и не имеют доступа к GitHub Runs, Artifacts и исходникам. Они оценивают внутреннюю согласованность утверждений и достаточность приведённых ссылок, но **не могут независимо подтвердить содержимое указанных Runs и Artifacts**. Они не должны заявлять о самостоятельной проверке первичных доказательств.

Если аудитор считает ссылку недостаточной — он пишет NEED INFO, а не делает вывод о факте.

Дата фиксации: 2026-11-14  
Main SHA: `de8b03b8c25f230ecbc58ec6670b57d834919fc0`  
Frozen Core blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` (совпадает с LOCKED)

---

## VERIFIED (с конкретным источником)

### Frozen Core
- `src/jamp/run.py`, blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` — совпадает с LOCKED SHA. Δ=0.

### Реализованные API-маршруты
По исходнику `src/jamp/api/app.py` на main:
- `POST /v1/verify` — строка 219
- `GET /v1/verdict/{verdict_id}` — строка 315
- `GET /v1/verdicts` — строка 346
- `GET /v1/verdicts/{verdict_id}/graph` — строка 398

Маршрут одного вердикта — `/v1/verdict/{verdict_id}`, не `/v1/verdicts/{id}`.

### Tenant Isolation (DEC-001)
Измерение 18 контролей:
- Passed: 14
- Skipped: 4 (`PROVIDER_NOT_CONFIGURED`, HTTP 503)
- Failed: 0, Errors: 0

По группам: Trace 6/6, UniversalVerdict 6/6, Verdict missing-record 2/2, Verdict positive/cross-organization 4 skipped.

Evidence: Run `41453863758`, Job `125305496915`, Artifact `13146565793`.

Статус: **ISOLATION_ENFORCED — NOT VERIFIED**. HOLD.

### Stage B v1 (Run 43411251104, Artifact 14029608135)
- Запланировано: 9 запросов.
- HTTP-successful requests: 8.
- Incomplete transport reads: 1 (Astra Task 2; HTTP status unknown).
- Классификация контента:
  - RESPONSE_COMPLETE: 3
  - RESPONSE_EMPTY: 4
  - RESPONSE_TRUNCATED: 1
  - INCOMPLETE_READ: 1
- Финансовая сверка: расчёт 28 369.5 units, наблюдение 28 371 units, разница 1.5.
- Astra Task 2: списание AMBIGUOUS (presumed 624, actual null).

### Stage B v2 (Run 43443336439, Job 131946326174, Artifact 14047328339)
- Targeted retry: 4 запроса (Nemotron T5, DeepSeek T1, T2, T5) с увеличенным max_tokens.
- Классификация: 3 RESPONSE_COMPLETE, 1 RESPONSE_EMPTY.
- Аномалия DeepSeek Task 2: запрошено max_tokens=8192, usage.completion_tokens=26647, usage.reasoning_tokens=8192, finish_reason=length, message.content=null/empty. Классификация `MODEL_INCOMPATIBLE_WITH_MAX_TOKENS_FORMAT` — рабочая метка наблюдаемого случая. Общая совместимость DeepSeek с AnyModel и семантика max_tokens остаются UNKNOWN.
- Финансовая сверка: расчёт 25 354 units, наблюдение 25 355 units, разница 1. RECONCILED_WITH_1_UNIT_VARIANCE. Относится только к 4 запросам v2.

### Stage B накопительно (9 задач × 3 модели)
- COMPLETE: 6 из 9 (по 2 на каждую модель: T1 и T5).
- Не COMPLETE: 3 (Astra T2 = INCOMPLETE_READ, не повторялся; DeepSeek T2 = EMPTY; Nemotron T2 = EMPTY в v1).
- Квалификация моделей: **NOT_STARTED**.

### PR #553 / C6.2
- PR #553 merged, merge SHA `488a02053903eeea4544524b8c97a30961a7de58` — факт слияния VERIFIED.
- Наличие реализации в main — OBSERVED.
- Функциональная и production-проверка C6.2 этим фактом не подтверждается; статус поведения — UNKNOWN.
- Статусы остальных частей Stage C в рамках этого Input Pack не устанавливаются. Полное закрытие Stage C — **UNKNOWN**.

### RB-007 (G1 race condition)
- PR #580, merge SHA `1cc27daea7390ebdde249d9f0572dacbbc46fcdd`.
- Post-merge CI на main:
  - Research Loop v0 Gate (job label): Run `43473333744`, Job `132050652019`, Conclusion SUCCESS, Artifact `14061932293`.
  - G1 Trusted Lineage (job label): Run `43473333551`, Job `132050659480`, Conclusion SUCCESS, Artifact `14061213138`.
  - Pytest (job label): Run `43473333482`, Job `132050651058`, Conclusion SUCCESS, Artifact `14062002527`.
- Fix в коде: `wait_for_terminal()` с таймаутом, fail-closed при failure, poll интервал.
- Доказательство работоспособности фикса на реальной гонке двух workflow (canary PR #581, G1 Run ID / Job ID / Artifact не подтверждены) — UNKNOWN.

### RB-008 (PostgreSQL warnings)
- PR #582, merge SHA `cb8f1d4ded8d60bf8e4446cacf017d03ef89c9c9`.
- Post-merge CI на main:
  - Research Loop v0 Gate (job label): Run `43478560528`, Job `132068761964`, Conclusion SUCCESS, Artifact `14062769879`.
  - G1 Trusted Lineage (job label): Run `43478560639`, Job `132068762368`, Conclusion SUCCESS, Artifact `14064227496`.
  - Pytest (job label): Run `43478560621`, Job `132068762478`, Conclusion SUCCESS, Artifact `14062819917`.
- Fix: healthcheck `pg_isready -U jamp -d jamp_test`.
- В проверенном post-merge Pytest логе warning `role "root" does not exist` не обнаружен.
- Ожидаемое FK-нарушение от `ON DELETE RESTRICT` присутствует.

---

## OBSERVED (изучено, но не является production evidence)

### Dashboard
- `src/jamp/server/web/routes.py` использует `Jinja2Templates`.
- `dashboard.html` подключает ECharts 5 через CDN.
- Production-работа (реальный браузер, трафик, latency) — не проверена.

### G1 verifier (`scripts/g1_verify.py`)
- В коде присутствуют: проверка newest run, terminal state, job ID, artifact, fail-closed.
- Является ли `trusted-lineage` обязательным Ruleset check сейчас — не проверено.

### EVERYNODE
- Документ `docs/everynode/EVERYNODE_FOUNDATION_v0.1.md`: статус DRAFT, NOT APPROVED, NOT IMPLEMENTED. Это относится к документу.
- Статус EVERYNODE как проекта в целом этим документом не устанавливается.

---

## UNKNOWN (не утверждается ни в какую сторону)

- Production-конфигурация AnyModel: rate limits, документированные коды ошибок, контракт `finish_reason`, схема `usage`. `/openapi.json` → 404 при unauthenticated probe.
- Полная формула ценообразования для всех 109 моделей каталога — не установлена.
- Реальный контракт ответа `chat/completions` — первый платный запрос не выполнен.
- Наличие платящих клиентов JAMP.
- Коммерческая валидация любого продуктового направления.
- Текущее состояние Ruleset 23974688 (обязательность G1) — не проверялось.
- Production DNS/доступность `src/jamp/server/` в развёрнутом виде.
- G1 canary PR #581: конкретный G1 Run ID / Job ID / Artifact, подтверждающий прохождение G1 с первой попытки без Re-run.
- Статус RB-005 в текущем `OPEN_OBLIGATIONS.md` — в этой сессии не проверен.

---

## KNOWN GAPS (явные, acknowledged)

- Commercial demand: не проверен ни для Code Trust Report, ни для Research Audit, ни для anti-counterfeit (RB-009).
- `OPEN_OBLIGATIONS.md` не обновлён записями о закрытии RB-007 и RB-008 — факт слияния PR и факт административного закрытия обязательства различаются.
- RB-009 (anti-counterfeit) — backlog, не начат; условие старта: первый платный клиент по текущему направлению.

---

## НЕ утверждается в этом документе

Не выводить из Input Pack следующее — это интерпретации, не факты:

- «JAMP нужен, потому что модели не могут сами обнаружить галлюцинации» — наблюдение одного эксперимента, не доказательство необходимости JAMP.
- «Stage B показал превосходство какой-либо модели» — квалификация не проводилась.
- «Tenant Isolation работает» — 14/18, 4 skipped, ISOLATION_ENFORCED NOT VERIFIED.
- «Stage C закрыт» — функциональный статус C6.2 не подтверждён этим Input Pack; остальное UNKNOWN.
- «Trust Layer архитектурно уникален» — новизна не проверялась.
- «DeepSeek нельзя использовать через AnyModel» — зафиксирован один аномальный случай; общая совместимость UNKNOWN.

---

## Что должен сделать аудитор

На основании только этого документа:
1. Указать, что в JAMP действительно работает (с опорой на VERIFIED).
2. Указать, что реализовано, но production-эффект неизвестен (OBSERVED/UNKNOWN).
3. Указать, какие gaps блокируют продукт, а какие — нет.
4. Предложить NEXT шаги с конкретным definition-of-done.
5. Для любого NEED INFO — назвать, какой именно источник нужен.

Ограничения аудита:
- Не придумывать факты за пределами этого документа.
- Не выдавать гипотезы за выводы.
- Не считать совпадение трёх ответов доказательством истины.
- Не заявлять о самостоятельной проверке GitHub Runs / Artifacts — этих артефактов у аудитора нет.
