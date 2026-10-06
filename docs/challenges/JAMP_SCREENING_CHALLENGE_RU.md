# JAMP Screening Challenge
## Deterministic Capability Router

**Время:** 1.5–2 часа  
**Язык:** Python 3.11+  
**Формат:** take-home / Git repository

## Цель

Реализовать небольшой deterministic Capability Router для JAMP.

Router получает задачу, проверяет evidence о capability и принимает решение:

- **EXECUTE** — выполнение разрешено;
- **REFUSE** — выполнение запрещено.

Главный принцип:

> **Отсутствие достаточного evidence не является разрешением на выполнение.**

`UNKNOWN` и `INCONCLUSIVE` никогда не должны автоматически превращаться в `EXECUTE`.

## 1. API

Реализуйте:

`POST /v1/route`

Пример запроса:

```json
{
  "task_id": "task-001",
  "required_capability": "text_generation",
  "payload": {
    "prompt": "Write a short product description"
  }
}
```

Пример результата:

```json
{
  "decision": "EXECUTE",
  "selected_provider": "provider_a",
  "evidence": {
    "capability": "text_generation",
    "status": "VERIFIED"
  },
  "routing_reason": "provider_a has VERIFIED evidence for the required capability"
}
```

Для отказа:

```json
{
  "decision": "REFUSE",
  "selected_provider": null,
  "evidence": {
    "capability": "text_generation",
    "status": "UNKNOWN"
  },
  "routing_reason": "required capability is not sufficiently verified"
}
```

## 2. Providers

Создайте минимум два mock provider:

- `provider_a`
- `provider_b`

Каждый provider должен иметь capability evidence.

Например:

```text
provider_a:
  text_generation = VERIFIED

provider_b:
  text_generation = UNKNOWN
```

Provider selection должен быть **детерминированным**.

Если несколько providers имеют `VERIFIED` evidence, используйте явно описанное deterministic правило, например lexicographic order.

## 3. Обязательные правила

Router должен реализовать:

| Evidence | Decision |
|---|---|
| `VERIFIED` | `EXECUTE` |
| `UNKNOWN` | `REFUSE` |
| `INCONCLUSIVE` | `REFUSE` |
| отсутствует | `REFUSE` |

Дополнительно:

- неизвестная capability → `REFUSE`;
- provider timeout/error → корректная обработка без скрытого успеха;
- отсутствие подходящего provider → `REFUSE`;
- routing result должен содержать evidence;
- routing result должен объяснять причину решения;
- одинаковый input должен давать одинаковый routing result.

### Negative case

Обязательно:

```text
provider_a = UNKNOWN
provider_b = UNKNOWN
→ REFUSE
```

И:

```text
provider_a = VERIFIED
provider_b = UNKNOWN
→ EXECUTE provider_a
```

Нельзя реализовывать:

```text
UNKNOWN → попробовать provider на удачу
```

## 4. Тесты

Используйте `pytest`.

Минимально должны присутствовать тесты для:

1. `VERIFIED → EXECUTE`;
2. `UNKNOWN → REFUSE`;
3. `INCONCLUSIVE → REFUSE`;
4. отсутствующего evidence → `REFUSE`;
5. неизвестной capability → `REFUSE`;
6. deterministic provider selection;
7. provider error;
8. provider timeout;
9. отсутствия fallback при `UNKNOWN`;
10. одинакового результата для одинакового input.

Determinism рекомендуется проверить минимум **100 одинаковыми запусками**.

## 5. Архитектура

Не требуется строить production platform.

Ожидается небольшая, понятная архитектура с разделением:

```text
API
 ↓
Capability Router
 ↓
Evidence / Capability Model
 ↓
Provider Adapter
```

Не помещайте всю логику в один endpoint или giant service class.

Provider-specific детали должны быть изолированы через adapter/interface.

## 6. README

README должен содержать:

- краткое описание решения;
- требования;
- запуск локально;
- запуск тестов;
- пример API request/response;
- описание routing policy;
- объяснение deterministic selection;
- описание поведения при `UNKNOWN` / `INCONCLUSIVE`;
- краткое описание архитектурных решений.

## 7. Docker

Предоставьте:

- `Dockerfile`;
- при необходимости `docker-compose.yml`;
- инструкцию запуска.

Решение должно запускаться без proprietary API keys.

## 8. Критерии оценки

**100 баллов:**

| Область | Баллы |
|---|---:|
| Correct routing semantics | 25 |
| Fail-closed behavior | 20 |
| Deterministic selection | 15 |
| Tests / edge cases | 15 |
| Architecture / separation of concerns | 10 |
| Evidence + provenance in result | 10 |
| README / reproducibility | 5 |

### Критические ошибки

Следующие решения существенно снижают оценку:

- `UNKNOWN → EXECUTE`;
- случайный provider fallback;
- недетерминированный routing;
- удаление/ослабление тестов ради PASS;
- hardcoded secrets;
- отсутствие тестов негативных сценариев;
- невозможность воспроизвести запуск.

## 9. Формат сдачи

Предоставьте Git repository со структурой примерно:

```text
jamp-screening/
├── app/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

Точная структура не обязательна.

В репозитории должны быть:

- исходный код;
- тесты;
- Docker configuration;
- README;
- история Git commits.

### Submission

Отправьте ссылку на repository и короткое сообщение:

- сколько времени заняло выполнение;
- что было реализовано;
- какие assumptions были сделаны;
- что вы бы улучшили при наличии дополнительного времени.
