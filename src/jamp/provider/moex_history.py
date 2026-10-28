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


def _expected_trading_days_approx(date_from: str, date_till: str) -> int | None:
    try:
        days = (dt.date.fromisoformat(date_till) - dt.date.fromisoformat(date_from)).days
    except (TypeError, ValueError):
        return None
    return max(0, round(days * 250 / 365))


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
    observed_max_high_date: str | None = None,
    observed_min_low: float | None = None,
    claimed_year: int | None = None,
    trading_days_in_claimed_year: int = 0,
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
        "observed_max_high_date": observed_max_high_date,
        "observed_min_low": observed_min_low,
        "claimed_year": claimed_year,
        "trading_days_in_claimed_year": trading_days_in_claimed_year,
        "trading_days_count": trading_days_count,
        "pages_fetched": diagnostics.pop("pages_fetched", 0),
        "total_rows": diagnostics.pop("total_rows", None),
        "expected_trading_days_approx": diagnostics.pop(
            "expected_trading_days_approx",
            _expected_trading_days_approx(date_from, date_till),
        ),
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
    claim_year: int | None = None,
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
            claimed_year=claim_year,
            reason="invalid_date_range",
            result="INCONCLUSIVE",
            parse_error="dates must be ordered YYYY-MM-DD values",
        )

    if claim_year is not None and (
        isinstance(claim_year, bool)
        or not isinstance(claim_year, int)
        or not 1000 <= claim_year <= 9999
    ):
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            claimed_price,
            date_from,
            date_till,
            tolerance_pct,
            claimed_year=claim_year,
            reason="invalid_claim_year",
            result="INCONCLUSIVE",
        )

    if not normalized_ticker or not normalized_ticker.replace(".", "").replace("-", "").isalnum():
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            claimed_price,
            date_from,
            date_till,
            tolerance_pct,
            claimed_year=claim_year,
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
            claimed_year=claim_year,
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
            claimed_year=claim_year,
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
            claimed_year=claim_year,
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
            claimed_year=claim_year,
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
            claimed_year=claim_year,
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
            claimed_year=claim_year,
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
            claimed_year=claim_year,
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
                    claimed_year=claim_year,
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
                claimed_year=claim_year,
                reason="invalid_issue_date",
                result="INCONCLUSIVE",
                http_status=200,
                parse_error=f"invalid ISSUEDATE: {issue_date}",
            )

    history_base_url = (
        f"{MOEX_ISS_BASE}/history/engines/stock/markets/shares/boards/TQBR/"
        f"securities/{urllib.parse.quote(normalized_ticker, safe='')}.json"
    )
    history_rows: list[dict[str, Any]] = []
    pages_fetched = 0
    total_rows: int | None = None
    page_size: int | None = None
    previous_index: int | None = None
    next_start = 0
    max_pages = 1
    pagination_stalled = False
    cursor_missing = False
    try:
        while pages_fetched < max_pages:
            params = {"from": date_from, "till": date_till, "iss.meta": "off"}
            if next_start:
                params["start"] = str(next_start)
            history_url = f"{history_base_url}?{urllib.parse.urlencode(params)}"
            history_payload = _get_json(history_url, timeout)
            page_rows = _table_rows(history_payload, "history")
            pages_fetched += 1

            cursor_payload = history_payload.get("history.cursor")
            if not isinstance(cursor_payload, dict):
                history_table = history_payload.get("history")
                cursor_payload = (
                    history_table.get("cursor") if isinstance(history_table, dict) else None
                )
            cursor_rows = (
                _table_rows({"cursor": cursor_payload}, "cursor")
                if isinstance(cursor_payload, dict)
                else []
            )
            if not cursor_rows:
                history_rows.extend(page_rows)
                cursor_missing = True
                break

            cursor = cursor_rows[0]
            try:
                page_index = cursor["INDEX"]
                page_total = cursor["TOTAL"]
                current_page_size = cursor["PAGESIZE"]
                if any(
                    isinstance(value, bool) or not isinstance(value, int)
                    for value in (page_index, page_total, current_page_size)
                ):
                    raise ValueError("history cursor values must be integers")
                if page_index < 0 or page_total < 0 or current_page_size <= 0:
                    raise ValueError("history cursor values are out of range")
            except (KeyError, TypeError, ValueError):
                history_rows.extend(page_rows)
                cursor_missing = True
                break

            if total_rows is None:
                total_rows = page_total
                page_size = current_page_size
                max_pages = max(1, math.ceil(total_rows / page_size))
            elif page_total != total_rows or current_page_size != page_size:
                history_rows.extend(page_rows)
                cursor_missing = True
                break

            if page_index != next_start or (
                previous_index is not None and page_index <= previous_index
            ):
                pagination_stalled = True
                break

            history_rows.extend(page_rows)
            next_index = page_index + current_page_size
            if next_index >= page_total:
                break
            previous_index = page_index
            next_start = next_index
    except urllib.error.HTTPError as exc:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            claimed_year=claim_year,
            reason="moex_history_unavailable_or_invalid",
            result="INCONCLUSIVE",
            http_status=exc.code,
            pages_fetched=pages_fetched,
            total_rows=total_rows,
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
            claimed_year=claim_year,
            reason="moex_history_unavailable_or_invalid",
            result="INCONCLUSIVE",
            **_failure_diagnostics(exc=exc),
            pages_fetched=pages_fetched,
            total_rows=total_rows,
            error_type=type(exc).__name__,
        )

    expected_days = _expected_trading_days_approx(date_from, date_till)
    if pagination_stalled:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            claimed_year=claim_year,
            reason="pagination_stalled",
            result="INCONCLUSIVE",
            http_status=200,
            trading_days_count=len(history_rows),
            pages_fetched=pages_fetched,
            total_rows=total_rows,
            expected_trading_days_approx=expected_days,
        )

    if cursor_missing:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            claimed_year=claim_year,
            reason="incomplete_history_fetch",
            result="INCONCLUSIVE",
            http_status=200,
            trading_days_count=len(history_rows),
            pages_fetched=pages_fetched,
            total_rows=total_rows,
            expected_trading_days_approx=expected_days,
            expected_approx=expected_days,
            received=len(history_rows),
        )

    if not history_rows:
        has_reported_rows = total_rows is not None and total_rows > 0
        reason = (
            "incomplete_history_fetch"
            if has_reported_rows
            else "no_data_in_claimed_year"
            if claim_year is not None
            else "no_data_in_range"
        )
        diagnostics = (
            {
                "expected_approx": expected_days,
                "received": 0,
            }
            if has_reported_rows
            else {}
        )
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            claimed_year=claim_year,
            reason=reason,
            result="INCONCLUSIVE",
            http_status=200,
            pages_fetched=pages_fetched,
            total_rows=total_rows,
            expected_trading_days_approx=expected_days,
            **diagnostics,
        )

    if expected_days is not None and len(history_rows) < expected_days * 0.5:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            claimed_year=claim_year,
            reason="incomplete_history_fetch",
            result="INCONCLUSIVE",
            http_status=200,
            trading_days_count=len(history_rows),
            pages_fetched=pages_fetched,
            total_rows=total_rows,
            expected_trading_days_approx=expected_days,
            expected_approx=expected_days,
            received=len(history_rows),
        )

    claim_history_rows = (
        history_rows
        if claim_year is None
        else [
            row
            for row in history_rows
            if str(row.get("TRADEDATE", ""))[:4] == str(claim_year)
        ]
    )
    if claim_year is not None and not claim_history_rows:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            claimed_year=claim_year,
            reason="no_data_in_claimed_year",
            result="INCONCLUSIVE",
            http_status=200,
            trading_days_count=len(history_rows),
            trading_days_in_claimed_year=0,
            pages_fetched=pages_fetched,
            total_rows=total_rows,
            expected_trading_days_approx=expected_days,
        )

    metadata_shortname = metadata.get("SHORTNAME")
    row_names = {
        str(row["SHORTNAME"]).strip()
        for row in claim_history_rows
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
            claimed_year=claim_year,
            reason="ticker_reassigned",
            result="INCONCLUSIVE",
            http_status=200,
            trading_days_count=len(history_rows),
            pages_fetched=pages_fetched,
            total_rows=total_rows,
            expected_trading_days_approx=expected_days,
            observed_shortnames=sorted(row_names),
            metadata_shortname=metadata_shortname,
        )

    highs = [
        float(row["HIGH"])
        for row in claim_history_rows
        if isinstance(row.get("HIGH"), (int, float))
        and not isinstance(row.get("HIGH"), bool)
        and math.isfinite(float(row["HIGH"]))
    ]
    lows = [
        float(row["LOW"])
        for row in claim_history_rows
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
            claimed_year=claim_year,
            reason="historical_high_unavailable",
            result="INCONCLUSIVE",
            http_status=200,
            trading_days_count=len(history_rows),
            pages_fetched=pages_fetched,
            total_rows=total_rows,
            expected_trading_days_approx=expected_days,
        )

    observed_max_high = max(highs)
    max_high_row = next(
        row
        for row in claim_history_rows
        if isinstance(row.get("HIGH"), (int, float))
        and not isinstance(row.get("HIGH"), bool)
        and math.isfinite(float(row["HIGH"]))
        and float(row["HIGH"]) == observed_max_high
    )
    observed_max_high_date = max_high_row.get("TRADEDATE")
    if isinstance(observed_max_high_date, str):
        try:
            parsed_high_date = dt.date.fromisoformat(observed_max_high_date)
            if parsed_high_date.isoformat() != observed_max_high_date:
                observed_max_high_date = None
        except ValueError:
            observed_max_high_date = None
    else:
        observed_max_high_date = None
    if observed_max_high_date is None:
        return E4_INCONCLUSIVE, _evidence(
            normalized_ticker,
            float(claimed_price),
            date_from,
            date_till,
            tolerance_pct,
            claimed_year=claim_year,
            reason="historical_high_date_unavailable",
            result="INCONCLUSIVE",
            http_status=200,
            observed_max_high=observed_max_high,
            trading_days_count=len(history_rows),
            trading_days_in_claimed_year=len(claim_history_rows) if claim_year is not None else 0,
            pages_fetched=pages_fetched,
            total_rows=total_rows,
            expected_trading_days_approx=expected_days,
        )
    details = _evidence(
        normalized_ticker,
        float(claimed_price),
        date_from,
        date_till,
        tolerance_pct,
        claimed_year=claim_year,
        reason=None,
        result="VERIFIED",
        observed_max_high=observed_max_high,
        observed_max_high_date=observed_max_high_date,
        observed_min_low=observed_min_low,
        trading_days_in_claimed_year=len(claim_history_rows) if claim_year is not None else 0,
        trading_days_count=len(history_rows),
        http_status=200,
        pages_fetched=pages_fetched,
        total_rows=total_rows,
        expected_trading_days_approx=expected_days,
    )
    if observed_max_high >= float(claimed_price) * (1 - tolerance_pct / 100):
        return E4_VERIFIED, details
    details["result"] = "CONTRADICTED"
    details["reason"] = "historical_max_below_claimed"
    return E4_CONTRADICTED, details
