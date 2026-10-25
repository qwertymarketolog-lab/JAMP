from __future__ import annotations

import json
import os
import re
import sys
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MOEX_URL = "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/SBER.json"
USER_AGENT = "JAMP-Trust-Layer/1.0"
PRICE_TOLERANCE = Decimal("0.01")


def clean_number(value: Any) -> Decimal | None:
    """Parse a single unambiguous number; never turn missing/invalid data into zero."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
        return number if number.is_finite() else None
    if not isinstance(value, str):
        return None

    text = value.strip().replace("\u00a0", " ").replace("\u202f", " ")
    text = text.replace("−", "-").replace("–", "-")
    text = re.sub(r"[$€£₽]", "", text)
    text = text.replace(" ", "").replace(",", "")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def get_value(columns: list[Any], row: list[Any], name: str) -> Any:
    try:
        return row[columns.index(name)]
    except (ValueError, IndexError):
        return None


def fetch_moex_reference() -> tuple[dict[str, Any], dict[str, Any]]:
    request = Request(MOEX_URL, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"MOEX returned HTTP {response.status}")
        payload = json.loads(response.read().decode("utf-8"))

    securities = payload.get("securities", {})
    marketdata = payload.get("marketdata", {})
    sec_rows = securities.get("data", [])
    md_rows = marketdata.get("data", [])
    if not sec_rows or not md_rows:
        raise ValueError("MOEX response has no security or marketdata row")

    sec_columns = securities.get("columns", [])
    md_columns = marketdata.get("columns", [])
    sec_row = sec_rows[0]
    md_row = md_rows[0]
    ticker = get_value(sec_columns, sec_row, "SECID")
    company = get_value(sec_columns, sec_row, "SHORTNAME")
    price = get_value(md_columns, md_row, "LAST")
    price_field = "LAST"
    if price is None:
        price = get_value(md_columns, md_row, "MARKETPRICE")
        price_field = "MARKETPRICE"

    numeric_price = clean_number(price)
    if ticker != "SBER":
        raise ValueError(f"Unexpected ticker in MOEX response: {ticker!r}")
    if not isinstance(company, str) or not company.strip():
        raise ValueError(f"MOEX company name is missing: {company!r}")
    if numeric_price is None or numeric_price <= 0:
        raise ValueError(
            "MOEX has no valid positive LAST/MARKETPRICE value "
            f"(field={price_field}, value={price!r})"
        )

    expected = {
        "ticker": ticker,
        "company": company.strip(),
        "price": str(numeric_price),
    }
    source_evidence = {
        "source": "MOEX ISS",
        "url": MOEX_URL,
        "fetched_at_utc": datetime.now(UTC).isoformat(),
        "price_field": price_field,
        "raw_price": price,
    }
    return expected, {"raw_payload": payload, "source_evidence": source_evidence}


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        value = None
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                value = candidate
                break
    if not isinstance(value, dict):
        raise ValueError("model output did not contain a JSON object")
    required = {"ticker", "company", "price"}
    if not required.issubset(value):
        raise ValueError(f"model JSON is missing required keys: {sorted(required - set(value))}")
    return value


def main() -> int:
    print("=== JAMP STOCK AUDIT EXPERIMENT (MOEX ISS) ===")
    try:
        expected, source = fetch_moex_reference()
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
        print(f"[MOEX SOURCE] FAIL — {type(exc).__name__}: {exc}")
        print("[MODEL VERIFIED] UNKNOWN — source data unavailable")
        print("[DATA MATCH] NOT RUN")
        print("[RESULT] HOLD")
        return 2

    print("[MOEX SOURCE] OBSERVED")
    print(
        json.dumps(
            {"reference": expected, **source["source_evidence"]},
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    prompt = (
        "Извлеки из следующего JSON Московской Биржи данные акции. "
        "Верни строго один JSON-объект без markdown и без пояснений с ключами "
        '"ticker", "company", "price". Не исправляй и не дополняй значения.\n'
        + json.dumps(source["raw_payload"], ensure_ascii=False, separators=(",", ":"))
    )
    base_url = os.environ.get("JAMP_API_URL", "http://127.0.0.1:8000").rstrip("/")
    request_body = json.dumps(
        {"intent": "search_and_extraction", "prompt": prompt},
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        f"{base_url}/v1/execute",
        data=request_body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=float(os.environ.get("JAMP_API_TIMEOUT", "90"))) as response:
            http_status = response.status
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        http_status = exc.code
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {"error": "non-JSON HTTP error response"}
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        print(f"[JAMP API] FAIL — {type(exc).__name__}: {exc}")
        print("[MODEL VERIFIED] UNKNOWN — no verifiable API response")
        print("[DATA MATCH] NOT RUN")
        print("[RESULT] HOLD")
        return 2

    trace_id = payload.get("trace_id", "UNKNOWN") if isinstance(payload, dict) else "UNKNOWN"
    evidence_status = payload.get("evidence_status") if isinstance(payload, dict) else None
    output = payload.get("output") if isinstance(payload, dict) else None
    if not isinstance(evidence_status, str) and isinstance(output, dict):
        evidence_status = output.get("evidence_status")
    print(f"trace_id: {trace_id}")
    print(f"evidence_status: {evidence_status or 'UNKNOWN'}")

    if (
        http_status < 200
        or http_status >= 300
        or not isinstance(payload, dict)
        or payload.get("status") != "EXECUTE"
    ):
        print("[MODEL VERIFIED] UNKNOWN — JAMP did not return an executable response")
        print("[DATA MATCH] NOT RUN")
        print("[DEBUG] JAMP response:")
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        print("[RESULT] HOLD")
        return 1

    if evidence_status == "VERIFIED":
        print("[MODEL VERIFIED] YES — evidence_status=VERIFIED")
    else:
        print(f"[MODEL VERIFIED] UNKNOWN/NO — evidence_status={evidence_status!r}")

    if not isinstance(output, dict) or not isinstance(output.get("content"), str):
        print("[DATA MATCH] FAIL — response.output.content is missing")
        print("[RESULT] HOLD")
        return 1
    try:
        extracted = parse_json_object(output["content"])
    except ValueError as exc:
        print(f"[DATA MATCH] FAIL — {exc}")
        print(f"raw_output: {output['content']}")
        print("[RESULT] FAIL")
        return 1

    print("[AI EXTRACTED JSON]")
    print(json.dumps(extracted, ensure_ascii=False, indent=2, sort_keys=True))

    mismatches: list[str] = []
    if (
        not isinstance(extracted.get("ticker"), str)
        or extracted["ticker"].strip().upper() != expected["ticker"]
    ):
        mismatches.append(
            f"ticker expected {expected['ticker']!r}, got {extracted.get('ticker')!r}"
        )
    if (
        not isinstance(extracted.get("company"), str)
        or extracted["company"].strip().casefold() != expected["company"].casefold()
    ):
        mismatches.append(
            f"company expected {expected['company']!r}, got {extracted.get('company')!r}"
        )
    actual_price = clean_number(extracted.get("price"))
    expected_price = clean_number(expected["price"])
    if actual_price is None or expected_price is None:
        mismatches.append(
            "price is not a valid number "
            f"(expected={expected['price']!r}, got={extracted.get('price')!r})"
        )
    elif abs(actual_price - expected_price) > PRICE_TOLERANCE:
        mismatches.append(f"price expected {expected_price}, got {actual_price}")

    if mismatches:
        print("[DATA MATCH] NO")
        for mismatch in mismatches:
            print(f"  - {mismatch}")
    else:
        print("[DATA MATCH] YES")

    if evidence_status != "VERIFIED":
        print("[RESULT] HOLD — E2 model identity was not VERIFIED")
        return 1
    if mismatches:
        print("[RESULT] FAIL — extracted values differ from MOEX reference")
        return 1
    print("[RESULT] PASS — E2 identity VERIFIED and values matched MOEX reference")
    return 0


if __name__ == "__main__":
    sys.exit(main())
