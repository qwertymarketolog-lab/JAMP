Ты — AI-1, независимый API Architect. Ответь строго в Markdown. Не предлагай и не пиши код. Если данных недостаточно — укажи "NEED INFO: ..." и не выдумывай факты.

Задача: архитектурный аудит C6 Dashboard API JAMP и минимальный контракт C6.1.

Подтверждённый контекст:
- C6 разделён на C6.1 Dashboard API и C6.2 Web Dashboard.
- Существуют POST /v1/verify, GET /v1/verdict/{verdict_id}, GET /v1/universal-verdict/{trace_id}, GET /v1/jamp-verdict/{trace_id}.
- GET /v1/verdicts (список) в проверенной версии не обнаружен.
- DB: organizations, audit_traces, verdicts, evidence_chain. Отдельной events-таблицы нет.
- Допустимые статусы verdicts: CLEAN, SUSPICIOUS, HALLUCINATION_CAUGHT, INCONCLUSIVE, INTEGRITY_VIOLATED.
- В JSON используется поле package, не package_name.
- evidence_chain: sequence_no, evidence_type, payload, payload_hash, created_at.
- Tenant isolation должна выполняться непосредственно в DB-запросах.

Проверь:
1. Read endpoints для экранов Overview, Researches, Evidence Graph, Checks, Conflicts, History, Models & Sources.
2. Схемы ответов и связи verdict → evidence → trace.
3. Пагинацию, сортировку, фильтры, стабильные курсоры и bounded limits.
4. Определения агрегатов, знаменатели и пустые выборки.
5. Tenant isolation, ошибки 401/403/404/5xx.
6. Доступные поля против отсутствующих; миграции и обратную совместимость.
7. Необходимость каждого endpoint и риск дублирования.

Формат:
- Executive assessment
- Existing API facts vs proposed API
- Endpoint matrix (экран → endpoint → данные)
- Minimal response contracts
- Security / tenant isolation
- Pagination and query semantics
- Missing data / NEED INFO
- P0 risks and recommendations

Отделяй факты контекста от предложений. Не утверждай, что endpoint или поле существует, если это не указано.
