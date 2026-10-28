"""Fact-only stock screener using MOEX ISS; this is not investment advice."""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MOEX_ISS_BASE = "https://iss.moex.com/iss"
DEFAULT_TICKERS = ["SMLT", "ALRS", "RTKM", "AFLT", "AFKS", "SGZH", "UWGN", "WUSH", "DELI", "SBER"]
SCREENING_PARAMS: dict[str, Any] = {
    "drawdown_threshold": 0.70,
    "date_from": "2013-01-01",
    "date_till": dt.date.today().isoformat(),
    "min_daily_volume_rub": 1_000_000,
    "min_trading_days": 500,
}
TIMEOUT_SECONDS = 10.0
PAGE_SIZE = 100


def _get_json(url: str, timeout: float = TIMEOUT_SECONDS) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "JAMP-Stock-Screener/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MOEX ISS response must be a JSON object")
    return payload


def _rows(payload: dict[str, Any], table_name: str) -> list[dict[str, Any]]:
    table = payload.get(table_name)
    if not isinstance(table, dict):
        raise ValueError(f"MOEX ISS response missing {table_name} table")
    columns, data = table.get("columns"), table.get("data")
    if not isinstance(columns, list) or not all(isinstance(c, str) for c in columns):
        raise ValueError(f"MOEX ISS {table_name} columns invalid")
    if not isinstance(data, list):
        raise ValueError(f"MOEX ISS {table_name} data invalid")
    return [
        dict(zip(columns, row, strict=True))
        for row in data
        if isinstance(row, list) and len(row) == len(columns)
    ]


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number > 0 else None


def _url(path: str, params: dict[str, Any]) -> str:
    return f"{MOEX_ISS_BASE}/{path}?{urllib.parse.urlencode(params)}"


def _security_metadata(ticker: str) -> dict[str, Any]:
    payload = _get_json(f"{MOEX_ISS_BASE}/securities/{urllib.parse.quote(ticker, safe='')}.json")
    rows = _rows(payload, "description")
    metadata = {str(row.get("name", "")).upper(): row.get("value") for row in rows}
    if str(metadata.get("SECID", "")).upper() != ticker:
        raise ValueError("exact ticker missing from MOEX security metadata")
    return metadata


def _current_price(ticker: str) -> float | None:
    payload = _get_json(
        _url(
            f"engines/stock/markets/shares/securities/{urllib.parse.quote(ticker, safe='')}.json",
            {"iss.meta": "off", "iss.only": "marketdata", "marketdata.columns": "SECID,LAST"},
        )
    )
    rows = _rows(payload, "marketdata")
    for row in rows:
        if str(row.get("SECID", "")).upper() == ticker:
            return _number(row.get("LAST"))
    return None


def _all_history(ticker: str) -> list[dict[str, Any]]:
    path = (
        f"history/engines/stock/markets/shares/boards/TQBR/"
        f"securities/{urllib.parse.quote(ticker, safe='')}.json"
    )
    collected: list[dict[str, Any]] = []
    start = 0
    expected_total: int | None = None
    page_size: int | None = None
    seen_starts: set[int] = set()
    while True:
        payload = _get_json(
            _url(
                path,
                {
                    "from": SCREENING_PARAMS["date_from"],
                    "till": SCREENING_PARAMS["date_till"],
                    "start": start,
                    "iss.meta": "off",
                    "history.columns": "BOARDID,TRADEDATE,SHORTNAME,SECID,HIGH,CLOSE,VALUE",
                    "history.cursor": "true",
                },
            )
        )
        page = _rows(payload, "history")
        collected.extend(page)
        cursor_rows = _rows(payload, "history.cursor")
        if not cursor_rows:
            if page:
                raise ValueError("history pagination cursor missing")
            if expected_total not in (None, 0):
                raise ValueError("history pagination incomplete")
            return collected
        cursor = cursor_rows[0]
        index, total, size = cursor.get("INDEX"), cursor.get("TOTAL"), cursor.get("PAGESIZE")
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (index, total, size)):
            raise ValueError("invalid history pagination cursor")
        if index != start or total < 0 or size <= 0 or start in seen_starts:
            raise ValueError("history pagination stalled or invalid")
        seen_starts.add(start)
        if expected_total is None:
            expected_total, page_size = total, size
        elif total != expected_total or size != page_size:
            raise ValueError("history pagination metadata changed")
        if len(page) == 0 and start < total:
            raise ValueError("empty page before reported history end")
        next_start = index + size
        if next_start >= total:
            if len(collected) < total:
                raise ValueError("history pagination returned fewer rows than reported")
            return collected
        start = next_start


def screen_ticker(ticker: str) -> dict[str, Any]:
    """Collect verifiable market facts for one ticker; never an investment recommendation."""
    normalized = ticker.strip().upper() if isinstance(ticker, str) else ""
    result: dict[str, Any] = {
        "ticker": normalized,
        "shortname": None,
        "max_high": None,
        "max_date": None,
        "current_price": None,
        "drawdown": None,
        "avg_daily_volume": None,
        "trading_days": 0,
        "flags": [],
        "verdict": "FAIL",
        "reason": None,
    }
    if not normalized or not normalized.replace(".", "").replace("-", "").isalnum():
        result["reason"] = "INVALID_TICKER"
        result["flags"].append("invalid_ticker")
        return result
    try:
        metadata = _security_metadata(normalized)
        shortname = metadata.get("SHORTNAME")
        result["shortname"] = shortname if isinstance(shortname, str) else None
        history = _all_history(normalized)
        current_price = _current_price(normalized)
    except urllib.error.HTTPError as exc:
        result["reason"] = f"MOEX_HTTP_ERROR_{exc.code}"
        result["flags"].append("source_error")
        return result
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        result["reason"] = f"MOEX_DATA_ERROR:{type(exc).__name__}"
        result["flags"].append("source_error")
        return result

    result["current_price"] = current_price
    valid_rows = [
        row for row in history
        if row.get("BOARDID") == "TQBR"
        and str(row.get("SECID", "")).upper() == normalized
        and isinstance(row.get("TRADEDATE"), str)
    ]
    result["trading_days"] = len({row["TRADEDATE"] for row in valid_rows})
    observed_names = {
        row["SHORTNAME"].strip()
        for row in valid_rows
        if isinstance(row.get("SHORTNAME"), str) and row["SHORTNAME"].strip()
    }
    if (
        not isinstance(shortname, str)
        or not shortname.strip()
        or len(observed_names) > 1
        or (observed_names and shortname.strip() not in observed_names)
    ):
        result["flags"].append("ticker_reassigned")
        result["verdict"] = "SKIP_REASSIGNED"
        result["reason"] = "SHORTNAME_MISMATCH"
        return result

    highs: list[tuple[float, str]] = []
    for row in valid_rows:
        high = _number(row.get("HIGH"))
        if high is not None:
            highs.append((high, row["TRADEDATE"]))
    if highs:
        max_high, max_date = max(highs, key=lambda item: item[0])
        result["max_high"] = max_high
        result["max_date"] = max_date
    values = [
        float(row["VALUE"])
        for row in valid_rows[-30:]
        if isinstance(row.get("VALUE"), (int, float))
        and not isinstance(row.get("VALUE"), bool)
        and math.isfinite(float(row["VALUE"]))
        and float(row["VALUE"]) >= 0
    ]
    usable_values = [value for value in values if value is not None]
    if len(usable_values) == 30:
        result["avg_daily_volume"] = sum(usable_values) / len(usable_values)

    if current_price is None:
        result["flags"].append("delisted_or_no_current_price")
        result["verdict"] = "SKIP_DELISTED"
        result["reason"] = "CURRENT_PRICE_UNAVAILABLE"
        return result
    if result["trading_days"] < SCREENING_PARAMS["min_trading_days"]:
        result["flags"].append("insufficient_history")
        result["verdict"] = "SKIP_INSUFFICIENT_HISTORY"
        result["reason"] = "TRADING_DAYS_BELOW_MINIMUM"
        return result
    if result["max_high"] is None or result["max_high"] <= 0:
        result["reason"] = "HISTORICAL_HIGH_UNAVAILABLE"
        result["flags"].append("incomplete_data")
        return result

    result["drawdown"] = (result["max_high"] - current_price) / result["max_high"]
    if result["avg_daily_volume"] is None:
        result["reason"] = "LAST_30_DAYS_VOLUME_INCOMPLETE"
        result["flags"].append("incomplete_data")
        return result
    if result["avg_daily_volume"] < SCREENING_PARAMS["min_daily_volume_rub"]:
        result["flags"].append("low_liquidity")
        result["verdict"] = "SKIP_LIQUIDITY"
        result["reason"] = "AVERAGE_DAILY_VOLUME_BELOW_MINIMUM"
        return result
    if result["drawdown"] >= SCREENING_PARAMS["drawdown_threshold"]:
        result["verdict"] = "PASS"
        result["reason"] = None
    else:
        result["verdict"] = "FAIL"
        result["reason"] = "DRAWDOWN_BELOW_THRESHOLD"
    return result


def screen(tickers: list[str]) -> dict[str, Any]:
    """Screen tickers and return facts plus explicit coverage accounting."""
    if not tickers:
        return {"tickers": [], "coverage": None, "params": dict(SCREENING_PARAMS)}
    results = [screen_ticker(ticker) for ticker in tickers]
    skips = sum(item["verdict"].startswith("SKIP_") for item in results)
    passes = sum(item["verdict"] == "PASS" for item in results)
    fails = sum(item["verdict"] == "FAIL" for item in results)
    return {
        "tickers": results,
        "coverage": {"pass": passes, "skip": skips, "fail": fails, "total": len(results)},
        "params": dict(SCREENING_PARAMS),
        "disclaimer": "Screening statistics only; not investment advice or a valuation conclusion.",
    }


def _markdown(report: dict[str, Any]) -> str:
    rows = [
        (
            "| Ticker | Company | Max high | Max date | Current | Drawdown | "
            "Avg daily volume (RUB) | Days | Verdict |"
        ),
        "|---|---|---:|---|---:|---:|---:|---:|---|",
    ]
    for item in report["tickers"]:
        drawdown = item["drawdown"]
        volume_value = item["avg_daily_volume"]
        volume = round(volume_value) if volume_value is not None else "—"
        rows.append(
            (
                "| {ticker} | {shortname} | {high} | {date} | {price} | "
                "| {drawdown} | {volume} | {days} | {verdict} |"
            ).format(
                ticker=item["ticker"],
                shortname=item["shortname"] or "—",
                high=item["max_high"] if item["max_high"] is not None else "—",
                date=item["max_date"] or "—",
                price=item["current_price"] if item["current_price"] is not None else "—",
                drawdown=f"{drawdown:.3f}" if drawdown is not None else "—",
                volume=volume,
                days=item["trading_days"],
                verdict=item["verdict"],
            )
        )
    return "\n".join(rows)


def main() -> int:
    raw_tickers = sys.stdin.read().strip()
    tickers = (
        [line.strip().upper() for line in raw_tickers.splitlines() if line.strip()]
        if raw_tickers
        else DEFAULT_TICKERS
    )
    report = screen(tickers)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print("\n" + _markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
