# JAMP — Trust Layer для AI

JAMP — API для независимой проверки отдельных фактических утверждений, извлечённых из текста, по внешним источникам данных. Для текущего клиентского API поддерживается ограниченная проверка цен: акции и другие инструменты MOEX в RUB, а также криптоактивы из поддерживаемого списка CoinGecko в USD.

JAMP не считает ответ AI доказательством. Для поддерживаемого ценового утверждения сервис извлекает кандидата, запрашивает независимый источник, сохраняет исходный HTTP-ответ в evidence и проверяет целостность тела по SHA-256. Если утверждение нельзя однозначно извлечь или подтвердить, результат остаётся `INCONCLUSIVE`.

## Quick Start

### 1. Получить API-ключ

Запросите доступ у оператора развёрнутого экземпляра JAMP. На текущий момент публичного self-service endpoint для выпуска API-ключей нет.

Ключ передаётся отдельно от запроса. Не помещайте его в URL, JSON body, репозиторий или логи. API определяет организацию по API-ключу; передавать `org_id` в теле запроса не нужно и нельзя.

### 2. Отправить проверку

Укажите адрес вашего развёрнутого экземпляра в `JAMP_BASE_URL`, а выданный ключ — в переменной окружения `JAMP_API_KEY`.

```bash
export JAMP_BASE_URL="https://your-jamp-host"
export JAMP_API_KEY="YOUR_API_KEY"

curl --fail-with-body --silent --show-error \
  -X POST "$JAMP_BASE_URL/v1/verify_claim" \
  -H "Authorization: Bearer $JAMP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Цена SBER 299.26 RUB"}'
```

Успешная HTTP-обработка возвращает JSON с одним из вердиктов:

- `VERIFIED` — источник подтвердил утверждение в пределах допуска;
- `CONTRADICTED` — источник противоречит утверждению за пределами допуска;
- `INCONCLUSIVE` — извлечение, источник или доказательство не позволяют вынести подтверждённый вердикт.

HTTP 200 сам по себе не означает VERIFIED: всегда проверяйте поле `verdict`.

## Поддерживаемые примеры

### MOEX — цена в RUB

```bash
curl --fail-with-body --silent --show-error \
  -X POST "$JAMP_BASE_URL/v1/verify_claim" \
  -H "Authorization: Bearer $JAMP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Цена SBER 299.26 RUB","tolerance_pct":1.0}'
```

### CoinGecko — цена криптоактива в USD

```bash
curl --fail-with-body --silent --show-error \
  -X POST "$JAMP_BASE_URL/v1/verify_claim" \
  -H "Authorization: Bearer $JAMP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Цена BTC 65000 USD","tolerance_pct":1.0}'
```

CoinGecko применяется только к тикерам, присутствующим во внутренней карте поддерживаемых криптоактивов. Это не универсальная проверка любых USD-цен.

## Формат ответа

Ниже — схема формы ответа, а не запись реального рыночного запроса. Конкретные значения `verdict`, `details` и `raw_evidence` зависят от ответа внешнего провайдера.

```json
{
  "verdict": "INCONCLUSIVE",
  "reason": "EXAMPLE_REASON",
  "extracted_claim": {
    "claim_id": "trace_c1",
    "type": "price",
    "value": 299.26,
    "unit": "RUB",
    "raw_text": "Цена SBER 299.26 RUB",
    "citation_url": null,
    "status": null,
    "source": null,
    "evidence": null,
    "critical": null
  },
  "details": {},
  "raw_evidence": [
    {
      "source": "moex.iss",
      "url": "https://iss.moex.com/...",
      "status_code": 200,
      "body_complete": true,
      "raw_body_base64": "<base64 исходного HTTP body>",
      "sha256_body": "<64 lowercase hex characters>"
    }
  ],
  "tolerance_pct": 1.0,
  "verification_mode": "DIRECT_E4_NO_E2"
}
```

`raw_evidence` содержит исходное тело ответа провайдера в Base64 и SHA-256 этого тела. Хеш позволяет клиенту независимо проверить, что сохранённые байты соответствуют указанному digest. При отсутствии или некорректности RAW-доказательства положительный/отрицательный вывод не повышается до `VERIFIED` или `CONTRADICTED`.

## Границы текущего API

- Один запрос рассчитан ровно на одно извлечённое утверждение. Если текст разбивается на ноль или несколько кандидатов, API возвращает `INCONCLUSIVE` с причиной `EXPECTED_EXACTLY_ONE_CLAIM`; пакетная проверка нескольких утверждений пока не поддерживается.
- Извлечение детерминированное и основано на правилах/регулярных выражениях. Это не универсальный NLP-парсер и не гарантия нахождения каждого утверждения в произвольном многостраничном анализе.
- Проверяются только поддерживаемые ценовые утверждения: RUB через MOEX и USD для криптоактивов из карты CoinGecko.
- API не проверяет прогнозы, инвестиционные рекомендации, причинно-следственные связи, историческую динамику, рыночные доли и произвольные факты.
- `VERIFIED` означает совпадение с полученными данными источника в рамках указанного допуска и зафиксированного ответа. Это не инвестиционная рекомендация и не гарантия будущей цены.
- Этот endpoint выполняет прямую проверку E4 и не запускает генерацию ответа AI.

## Полная спецификация

См. [docs/api_spec.md](docs/api_spec.md): request/response contract, authentication, provider-specific примеры, RAW evidence и HTTP errors.

## Лицензия и права

Исходный код JAMP распространяется по лицензии **GNU Affero General Public License v3.0 only (AGPL-3.0-only)**. См. [LICENSE](LICENSE).

Политика интеллектуальной собственности и лицензирования проекта описана в [docs/legal/JAMP-IP-LICENSING-POLICY.md](docs/legal/JAMP-IP-LICENSING-POLICY.md); сведения об авторских правах и уведомлениях — в [COPYRIGHT](COPYRIGHT) и [NOTICE](NOTICE).

Название и знаки JAMP отделены от лицензии программного обеспечения. Регистрация товарного знака является отдельной юридической процедурой.
