"""Bounded factual verification against the Moscow Exchange ISS API.

This module verifies only explicit claims about a MOEX security. A missing ticker
is OUT_OF_SCOPE, never proof that a company does not exist.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MOEX_ISS_BASE = "https://iss.moex.com/iss"
E4_VERIFIED = "E4_VERIFIED"
E4_CONTRADICTED = "E4_CONTRADICTED"
E4_OUT_OF_SCOPE = "E4_OUT_OF_SCOPE"
E4_INCONCLUSIVE = "E4_INCONCLUSIVE"


def _get_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "JAMP-Trust-Layer/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MOEX ISS response must be a JSON object")
    return payload


def _table_rows(payload: dict[str, Any], table_name: str) -> list[dict[str, Any]]:
    table = payload.get(table_name)
    if not isinstance(table, dict):
        raise ValueError(f"MOEX ISS response missing {table_name} table")
    columns = table.get("columns")
    rows = table.get("data")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise ValueError(f"MOEX ISS {table_name} table has invalid schema")
    if any(not isinstance(column, str) for column in columns):
        raise ValueError(f"MOEX ISS {table_name} columns are invalid")
    result: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, list) and len(row) == len(columns):
            result.append(dict(zip(columns, row, strict=True)))
    return result


def verify_claim_with_moex(
    ticker: str,
    claim_type: str,
    claimed_value: float | int | None,
    *,
    timeout: float = 5.0,
    price_tolerance: float = 0.05,
) -> tuple[str, dict[str, Any]]:
    """Verify an explicit MOEX ticker or last-price claim.

    Returns one of E4_VERIFIED, E4_CONTRADICTED, E4_OUT_OF_SCOPE, or
    E4_INCONCLUSIVE together with bounded source evidence.
    """
    normalized_ticker = ticker.strip().upper() if isinstance(ticker, str) else ""
    if not normalized_ticker or not normalized_ticker.replace(".", "").replace("-", "").isalnum():
        return E4_INCONCLUSIVE, {"reason": "INVALID_TICKER", "checked_source": "moex.iss"}
    if claim_type not in {"exists", "price"}:
        return E4_INCONCLUSIVE, {
            "reason": "UNSUPPORTED_CLAIM_TYPE",
            "claim_type": claim_type,
            "checked_source": "moex.iss",
        }
    if timeout <= 0 or not math.isfinite(timeout):
        return E4_INCONCLUSIVE, {"reason": "INVALID_TIMEOUT", "checked_source": "moex.iss"}
    if not math.isfinite(price_tolerance) or not 0 <= price_tolerance < 1:
        return E4_INCONCLUSIVE, {"reason": "INVALID_PRICE_TOLERANCE", "checked_source": "moex.iss"}
    if claim_type == "price" and (
        isinstance(claimed_value, bool)
        or not isinstance(claimed_value, (int, float))
        or not math.isfinite(float(claimed_value))
        or float(claimed_value) <= 0
    ):
        return E4_INCONCLUSIVE, {
            "reason": "INVALID_CLAIMED_PRICE",
            "claim": {"ticker": normalized_ticker, "type": claim_type, "value": claimed_value},
            "checked_source": "moex.iss",
        }

    query = urllib.parse.urlencode(
        {
            "q": normalized_ticker,
            "iss.meta": "off",
            "iss.only": "securities",
            "securities.columns": "secid,shortname,latinname,emitent_title",
        }
    )
    try:
        catalog = _get_json(f"{MOEX_ISS_BASE}/securities.json?{query}", timeout)
        securities = _table_rows(catalog, "securities")
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        return E4_INCONCLUSIVE, {
            "reason": "MOEX_SOURCE_UNAVAILABLE_OR_INVALID",
            "error_type": type(exc).__name__,
            "checked_source": "moex.iss",
        }

    match = next(
        (
            row
            for row in securities
            if isinstance(row.get("secid"), str) and row["secid"].upper() == normalized_ticker
        ),
        None,
    )
    if match is None:
        return E4_OUT_OF_SCOPE, {
            "claim": {"ticker": normalized_ticker, "type": claim_type, "value": claimed_value},
            "checked_source": "moex.iss",
            "result": "OUT_OF_SCOPE",
            "reason": (
                "Ticker not found in MOEX catalog; cannot verify existence of unlisted "
                "or foreign company"
            ),
        }

    if claim_type == "exists":
        return E4_VERIFIED, {
            "claim": {"ticker": normalized_ticker, "type": "exists"},
            "checked_source": "moex.iss",
            "result": "VERIFIED",
            "security": match,
        }

    price_query = urllib.parse.urlencode(
        {
            "iss.meta": "off",
            "iss.only": "marketdata",
            "marketdata.columns": "SECID,LAST,BOARDID,TRADEDATE",
        }
    )
    price_url = (
        f"{MOEX_ISS_BASE}/engines/stock/markets/shares/securities/"
        f"{urllib.parse.quote(normalized_ticker, safe='')}.json?{price_query}"
    )
    try:
        market = _get_json(price_url, timeout)
        market_rows = _table_rows(market, "marketdata")
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        return E4_INCONCLUSIVE, {
            "reason": "MOEX_MARKETDATA_UNAVAILABLE_OR_INVALID",
            "error_type": type(exc).__name__,
            "claim": {"ticker": normalized_ticker, "type": "price", "value": claimed_value},
            "checked_source": "moex.iss",
        }

    candidates = [
        row
        for row in market_rows
        if isinstance(row.get("SECID"), str)
        and row["SECID"].upper() == normalized_ticker
        and isinstance(row.get("LAST"), (int, float))
        and not isinstance(row.get("LAST"), bool)
        and math.isfinite(float(row["LAST"]))
        and float(row["LAST"]) > 0
    ]
    if not candidates:
        return E4_INCONCLUSIVE, {
            "reason": "MOEX_LAST_PRICE_UNAVAILABLE",
            "claim": {"ticker": normalized_ticker, "type": "price", "value": claimed_value},
            "checked_source": "moex.iss",
            "security": match,
        }

    latest = candidates[0]
    last_price = float(latest["LAST"])
    claimed_price = float(claimed_value)
    relative_delta = abs(claimed_price - last_price) / last_price
    details = {
        "claim": {"ticker": normalized_ticker, "type": "price", "value": claimed_price},
        "checked_source": "moex.iss",
        "observed_last": last_price,
        "relative_delta": relative_delta,
        "tolerance": price_tolerance,
        "board_id": latest.get("BOARDID"),
        "trade_date": latest.get("TRADEDATE"),
    }
    if relative_delta > price_tolerance:
        return E4_CONTRADICTED, {**details, "result": "CONTRADICTED"}
    return E4_VERIFIED, {**details, "result": "VERIFIED"}
