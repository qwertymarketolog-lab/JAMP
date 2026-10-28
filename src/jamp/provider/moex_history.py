"""Historical-price verification against MOEX ISS history."""

from __future__ import annotations

import datetime as dt
import math
import urllib.error
import urllib.parse
from typing import Any

from jamp.provider.moex_verify import (
    E4_CONTRADICTED,
    E4_INCONCLUSIVE,
    E4_VERIFIED,
    MOEX_ISS_BASE,
    _failure_diagnostics,
    _get_json,
    _table_rows,
)

DEFAULT_TIMEOUT = 5.0


def _evidence(
    ticker: str,
    claimed_price: float,
    date_from: str,
    date_till: str,
    tolerance_pct: float,
    *,
    reason: str | None,
    result: str,
    observed_max_high: float | None = None,
    observed_min_low: float | None = None,
    trading_days_count: int = 0,
    http_status: int | None = None,
    parse_error: str | None = None,
    tried_fields: list[str] | None = None,
    **diagnostics: Any,
) -> dict[str, Any]:
    return {
        "checked_source": "moex.iss.history",
        "claim": {
            "ticker": ticker,
            "type": "historical_price",
            "value": claimed_price,
        },
        "date_from": date_from,
        "date_till": date_till,
        "tolerance_pct": tolerance_pct,
        "observed_max_high": observed_max_high,
        "observed_min_low": observed_min_low,
        "trading_days_count": trading_days_count,
        "result": result,
        "reason": reason,
        **_failure_diagnostics(
            http_status=http_status,
            parse_error=parse_error,
            tried_fields=tried_fields or ["HIGH"],
        ),
        **diagnostics,
    }


def verify_historical_price(
    ticker: str,
    claimed_price: float,
    date_from: str,
    date_till: str,
    tolerance_pct: float = 2.0,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[str, dict[str, Any]]:
    """Verify whether a security reached a claimed price in a date range."""
    normalized_ticker = ticker.strip().upper() if isinstance(ticker, str) else ""
    try:
        start = dt.date.fromisoformat(date_from)
        end = dt.date.fromisoformat(date_till)
        if start.isoformat() != date_from or end.isoformat() != date_till or start > end:
            raise ValueError("dates must be ordered YYYY-MM-DD values")
    except (TypeError, ValueError):
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            claimed_price,
            str(date_from),
            str(date_till),
            tolerance_pct,
            reason="invalid_date_range",
            result="INCONCLUSIVE",
            parse_error="dates must be ordered YYYY-MM-DD values",
        )

    if not normalized_ticker or not normalized_ticker.replace(".", "").replace("-", "").isalnum():
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            claimed_price,
            date_from,
            date_till,
            tolerance_pct,
            reason="invalid_ticker",
            result="INCONCLUSIVE",
        )
    if (
        isinstance(claimed_price, bool)
        or not isinstance(claimed_price, (int, float))
        or not math.isfinite(float(claimed_price))
        or float(claimed_price) <= 0
    ):
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            claimed_price,
            date_from,
            date_till,
            tolerance_pct,
            reason="invalid_claimed_price",
            result="INCONCLUSIVE",
        )
    if not math.isfinite(tolerance_pct) or not 0 <= tolerance_pct < 100:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            claimed_price,
            date_from,
            date_till,
            tolerance_pct,
            reason="invalid_tolerance_pct",
            result="INCONCLUSIVE",
        )
    if not math.isfinite(timeout) or timeout <= 0:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            claimed_price,
            date_from,
            date_till,
            tolerance_pct,
            reason="invalid_timeout",
            result="INCONCLUSIVE",
        )

    security_url = (
        f"{MOEX_ISS_BASE}/securities/{urllib.parse.quote(normalized_ticker, safe='')}.json"
    )
    try:
        security_payload = _get_json(security_url, timeout)
        description = _table_rows(security_payload, "description")
        metadata = {
            str(row.get("name", "")).upper(): row.get("value")
            for row in description
            if row.get("name") is not None
        }
    except urllib.error.HTTPError as exc:
        reason = (
            "ticker_not_found_in_catalog"
            if exc.code == 404
            else "moex_source_unavailable_or_invalid"
        )
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            reason=reason,
            result="INCONCLUSIVE",
            http_status=exc.code,
            error_type=type(exc).__name__,
        )
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as exc:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            reason="moex_source_unavailable_or_invalid",
            result="INCONCLUSIVE",
            **_failure_diagnostics(exc=exc),
            error_type=type(exc).__name__,
        )

    if not metadata or not metadata.get("SECID"):
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            reason="ticker_not_found_in_catalog",
            result="INCONCLUSIVE",
            http_status=200,
        )
    if str(metadata.get("SECID", "")).upper() != normalized_ticker:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            reason="ticker_not_found_in_catalog",
            result="INCONCLUSIVE",
            http_status=200,
        )

    issue_date = metadata.get("ISSUEDATE")
    if isinstance(issue_date, str):
        try:
            if start < dt.date.fromisoformat(issue_date[:10]):
                return E4_INCONCLUSIVE, _evidence(
                    normalized_ticker,
                    float(claimed_price),
                    date_from,
                    date_till,
                    tolerance_pct,
                    reason="ticker_not_yet_existed",
                    result="INCONCLUSIVE",
                    http_status=200,
                )
        except ValueError:
            return E4_INCONCLUSIVE, _evidence(
                normalized_ticker,
                float(claimed_price),
                date_from,
                date_till,
                tolerance_pct,
                reason="invalid_issue_date",
                result="INCONCLUSIVE",
                http_status=200,
                parse_error=f"invalid ISSUEDATE: {issue_date}",
            )

    query = urllib.parse.urlencode({"from": date_from, "till": date_till, "iss.meta": "off"})
    history_url = (
        f"{MOEX_ISS_BASE}/history/engines/stock/markets/shares/boards/TQBR/"
        f"securities/{urllib.parse.quote(normalized_ticker, safe='')}.json?{query}"
    )
    try:
        history_payload = _get_json(history_url, timeout)
        history_rows = _table_rows(history_payload, "history")
    except urllib.error.HTTPError as exc:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            reason="moex_history_unavailable_or_invalid",
            result="INCONCLUSIVE",
            http_status=exc.code,
            error_type=type(exc).__name__,
        )
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as exc:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            reason="moex_history_unavailable_or_invalid",
            result="INCONCLUSIVE",
            **_failure_diagnostics(exc=exc),
            error_type=type(exc).__name__,
        )

    if not history_rows:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            reason="no_data_in_range",
            result="INCONCLUSIVE",
            http_status=200,
        )

    metadata_shortname = metadata.get("SHORTNAME")
    row_names = {
        str(row["SHORTNAME"]).strip()
        for row in history_rows
        if isinstance(row.get("SHORTNAME"), str) and row["SHORTNAME"].strip()
    }
    if len(row_names) > 1 or (
        metadata_shortname and row_names and str(metadata_shortname).strip() not in row_names
    ):
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            reason="ticker_reassigned",
            result="INCONCLUSIVE",
            http_status=200,
            trading_days_count=len(history_rows),
            observed_shortnames=sorted(row_names),
            metadata_shortname=metadata_shortname,
        )

    highs = [
        float(row["HIGH"])
        for row in history_rows
        if isinstance(row.get("HIGH"), (int, float))
        and not isinstance(row.get("HIGH"), bool)
        and math.isfinite(float(row["HIGH"]))
    ]
    lows = [
        float(row["LOW"])
        for row in history_rows
        if isinstance(row.get("LOW"), (int, float))
        and not isinstance(row.get("LOW"), bool)
        and math.isfinite(float(row["LOW"]))
    ]
    if not highs:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            reason="historical_high_unavailable",
            result="INCONCLUSIVE",
            http_status=200,
            trading_days_count=len(history_rows),
        )

    observed_max_high = max(highs)
    observed_min_low = min(lows) if lows else None
    details = _evidence(
        normalized_ticker,
        float(claimed_price),
        date_from,
        date_till,
        tolerance_pct,
        reason=None,
        result="VERIFIED",
        observed_max_high=observed_max_high,
        observed_min_low=observed_min_low,
        trading_days_count=len(history_rows),
        http_status=200,
    )
    if observed_max_high >= float(claimed_price) * (1 - tolerance_pct / 100):
        return E4_VERIFIED, details
    details["result"] = "CONTRADICTED"
    details["reason"] = "historical_max_below_claimed"
    return E4_CONTRADICTED, details
