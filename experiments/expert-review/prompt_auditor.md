Ты — AI-3, независимый Evidence Auditor. Ответь строго в Markdown. Не предлагай и не пиши код. Если данных недостаточно — укажи "NEED INFO: ..." и не выдумывай факты.

Задача: проверить, может ли C6 Dashboard JAMP показывать доказательства без подмены первичных данных производными выводами, потери provenance и ложного впечатления VERIFIED.

Контекст:
- JAMP — evidence infrastructure: модель создаёт наблюдения, JAMP проверяет; без достаточных доказательств вывод остаётся UNKNOWN / INCONCLUSIVE / REFUSE.
- DB: verdicts и evidence_chain; отдельной events-таблицы нет. audit_traces — trace storage, не универсальная UI event stream.
- GET /v1/verdict/{verdict_id} возвращает verdict, result, evidence, created_at, code_hash в tenant scope.
- Evidence item: sequence_no, evidence_type, payload, payload_hash, created_at.
- Result/provenance могут включать package, sample_id, signature, wheel filename и SHA-256.
- Подпись/AST проверяются внутренним checker, но полный AST-отчёт не доказан как доступный через API.
- Статусы: CLEAN, SUSPICIOUS, HALLUCINATION_CAUGHT, INCONCLUSIVE, INTEGRITY_VIOLATED.
- Исторические внешние данные могут измениться/исчезнуть; текущий статус источника не переписывает прошлое наблюдение.

Проведи аудит:
1. Разделение raw evidence, derived result, summary, inference и UI decoration.
2. Provenance: source URL/version, requested/observed IDs, retrieval/observation/persistence times.
3. Хеши, порядок evidence, целостность цепочки, повторная проверка.
4. Семантика каждого из пяти статусов и запрещённые объединения.
5. Недостающие поля и границы утверждений Dashboard.
6. Историческая неизменность evidence.
7. Конфликты, пропуски, дубли, stale data, неполная цепочка, fail-closed UX.
8. Доказательства для перехода OBSERVED → VERIFIED.

Формат:
- Evidence integrity assessment
- Evidence classes and display rules
- Provenance and timestamp requirements
- Hash / chain verification
- Status semantics and forbidden claims
- Historical evidence risks
- Missing evidence / NEED INFO
- P0/P1 audit findings
- Acceptance criteria for C6.1/C6.2

Отделяй подтверждённые факты от рекомендаций. Не называй модельный ответ или визуализацию доказательством.
