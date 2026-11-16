# JAMP Client API Specification

**API version:** v1  
**Endpoint:** `POST /v1/verify_claim`  
**Authentication:** HTTP Bearer API key  
**Content-Type:** `application/json`

This document describes the implemented endpoint contract. It does not define a multi-claim batch API.

## 1. Authentication and organization context

Send the API key in the HTTP Authorization header:

```http
Authorization: Bearer <API_KEY>
```

The API resolves the organization from the authenticated key. Do not send `org_id`; it is not an accepted request property. Unknown request properties are rejected with HTTP 422.

API keys are provisioned by the operator of the deployed JAMP instance. The current API does not expose a self-service key-creation endpoint. The application requires `JAMP_API_KEY_HASH_SECRET` at startup; a missing secret prevents startup. The plaintext API key must be handled out-of-band and must never be committed or logged.

## 2. Request schema

### JSON object

| Field | Type | Required | Default | Constraints |
|---|---|---:|---:|---|
| `text` | string | yes | — | Must contain at least one non-whitespace character |
| `tolerance_pct` | number | no | `1.0` | `0 <= value < 100`; booleans are rejected |

Additional properties are not allowed.

### Example

```json
{
  "text": "Цена SBER 299.26 RUB",
  "tolerance_pct": 1.0
}
```

The following user-proposed shape is **not** valid because `org_id` is not accepted and organization identity comes from the API key:

```json
{
  "text": "Цена SBER 299.26 RUB",
  "org_id": "test_org"
}
```

## 3. Extraction and verification contract

The endpoint deterministically extracts candidate claims from the supplied text.

- Exactly one candidate is required for provider verification.
- Zero or multiple candidates produce HTTP 200 with `verdict: INCONCLUSIVE`, `reason: EXPECTED_EXACTLY_ONE_CLAIM`, and no provider evidence.
- The candidate must be classified as a price claim and contain an identifiable ticker, numeric value, and supported currency.
- RUB claims are routed to MOEX ISS.
- USD claims are routed to CoinGecko only when the extracted ticker exists in the service's supported crypto ticker map.
- Unsupported claim types, missing fields, unsupported tickers/currencies, and provider errors fail closed as `INCONCLUSIVE`.

The extractor is rule-based. Do not treat it as a general-purpose parser for arbitrary AI reports.

## 4. Response schema

The endpoint returns HTTP 200 for completed verification attempts, including semantic `INCONCLUSIVE` outcomes.

| Field | Type | Meaning |
|---|---|---|
| `verdict` | string enum | `VERIFIED`, `CONTRADICTED`, or `INCONCLUSIVE` |
| `reason` | string or null | Reason code/detail when no conclusive verdict is available |
| `extracted_claim` | object or array or null | Extracted candidate mapped to the E4 claim shape; array is returned when multiple candidates were found |
| `details` | object, when provider verification ran | Provider-specific comparison and diagnostics |
| `raw_evidence` | array | Captured raw provider HTTP responses; empty when no provider call/evidence was produced |
| `tolerance_pct` | number | Effective tolerance supplied to the endpoint |
| `verification_mode` | string | Currently `DIRECT_E4_NO_E2` |

### Extracted claim object

| Field | Type |
|---|---|
| `claim_id` | string |
| `type` | string |
| `value` | number or null |
| `unit` | `RUB`, `USD`, or `UNKNOWN` |
| `raw_text` | string |
| `citation_url` | string or null |
| `status` | null in the extraction projection |
| `source` | null in the extraction projection |
| `evidence` | null in the extraction projection |
| `critical` | null in the extraction projection |

The final verdict and provider comparison are represented by the top-level `verdict`, `reason`, and `details` fields. Do not infer the verdict from the extraction projection's `status`.

### RAW evidence item

| Field | Type | Meaning |
|---|---|---|
| `source` | string | Provider identifier, e.g. `moex.iss` or `coingecko` |
| `url` | string | Provider request URL |
| `status_code` | integer | HTTP status received from provider |
| `body_complete` | boolean | Whether the complete response body was captured |
| `raw_body_base64` | string | Exact response body bytes encoded as Base64 |
| `sha256_body` | string | Lowercase SHA-256 hex digest of the exact body bytes |

Clients can independently validate the digest by Base64-decoding `raw_body_base64` and computing SHA-256 over the resulting bytes. The API checks body completeness, provider status 200, and digest consistency before returning `VERIFIED` or `CONTRADICTED`.

### Response shape (illustrative schema only; not live provider evidence)

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
      "raw_body_base64": "<base64 response bytes>",
      "sha256_body": "<64 lowercase hex characters>"
    }
  ],
  "tolerance_pct": 1.0,
  "verification_mode": "DIRECT_E4_NO_E2"
}
```

The response example deliberately uses `INCONCLUSIVE`; placeholder evidence values are not a claim that a live provider request has been performed.

## 5. cURL examples

Set the deployed service URL and provisioned key:

```bash
export JAMP_BASE_URL="https://your-jamp-host"
export JAMP_API_KEY="YOUR_API_KEY"
```

### MOEX / RUB

```bash
curl --fail-with-body --silent --show-error \
  -X POST "$JAMP_BASE_URL/v1/verify_claim" \
  -H "Authorization: Bearer $JAMP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Цена SBER 299.26 RUB","tolerance_pct":1.0}'
```

### CoinGecko / USD

```bash
curl --fail-with-body --silent --show-error \
  -X POST "$JAMP_BASE_URL/v1/verify_claim" \
  -H "Authorization: Bearer $JAMP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Цена BTC 65000 USD","tolerance_pct":1.0}'
```

CoinGecko USD verification is for supported cryptocurrency tickers (for example BTC), not arbitrary USD-denominated equities.

## 6. HTTP errors and fail-closed outcomes

### Endpoint/authentication responses

| HTTP status | Condition | Contract |
|---:|---|---|
| 200 | Verification completed or could not reach a conclusive semantic result | Inspect `verdict`; HTTP 200 is not equivalent to `VERIFIED` |
| 401 | Missing or invalid Bearer API key | Authentication rejected |
| 403 | API key belongs to a disabled organization | Access denied |
| 422 | Empty/missing text, invalid `tolerance_pct`, malformed request body, or unsupported extra request fields | Request rejected |
| 503 | Database unavailable during API-key lookup | Service unavailable |

The current handler does not define a stable endpoint-specific HTTP 400 or HTTP 500 response contract. Do not rely on either status as a documented business response. Unexpected provider exceptions caught by the handler are returned as HTTP 200 with `verdict: INCONCLUSIVE` and a `PROVIDER_ERROR:<ExceptionType>` reason. Infrastructure failures outside that handler may be surfaced by the serving stack.

### Common INCONCLUSIVE reasons

- `CLAIM_EXTRACTION_FAILED`
- `EXPECTED_EXACTLY_ONE_CLAIM`
- `CLAIM_TYPE_NOT_SUPPORTED`
- `MISSING_TICKER_VALUE_OR_CURRENCY`
- `UNKNOWN_COINGECKO_TICKER`
- `PROVIDER_ERROR:<ExceptionType>`
- `RAW_EVIDENCE_MISSING_OR_INVALID`

## 7. Scope and non-goals

The current endpoint verifies a single, explicit price assertion:

- RUB: MOEX ISS instruments supported by the provider implementation.
- USD: supported crypto assets mapped to CoinGecko.

It does not verify forecasts, investment advice, causal explanations, historical percentage movements, market-share claims, or arbitrary factual statements. It does not establish that a price will persist after the source response was retrieved. It does not currently batch multiple claims from a long report.

## 8. Operational notes

- The API key is sent only in the Authorization header over HTTPS.
- The organization context is derived from the key; callers cannot select another organization using `org_id`.
- Keep the API key and `JAMP_API_KEY_HASH_SECRET` out of source control and logs.
- Use the `verdict` field, not the HTTP status alone, to decide whether a claim was verified.
- Preserve the full response, including RAW evidence, when an auditable client-side record is required.
