from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from jamp.provider.moex_history import (
    E4_CONTRADICTED,
    E4_INCONCLUSIVE,
    E4_VERIFIED,
    verify_historical_price,
)


def _response(payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return MagicMock(__enter__=MagicMock(return_value=response))


def _description(*, issue_date="2007-07-20", shortname="Сбербанк"):
    rows = [
        ["SECID", "Идентификатор ценной бумаги", "SBER"],
        ["ISSUEDATE", "Дата начала торгов", issue_date],
        ["LISTLEVEL", "Уровень листинга", 1],
        ["SHORTNAME", "Краткое наименование", shortname],
        ["EMITTER_ID", "Идентификатор эмитента", 484],
    ]
    return {"description": {"columns": ["name", "title", "value"], "data": rows}}


def _history(*rows, cursor=None):
    if cursor is None:
        cursor = (0, len(rows), 100)
    cursor_rows = [list(cursor)] if cursor else []
    return {
        "history": {
            "columns": ["BOARDID", "TRADEDATE", "SHORTNAME", "SECID", "LOW", "HIGH", "CLOSE"],
            "data": list(rows),
        },
        "history.cursor": {
            "columns": ["INDEX", "TOTAL", "PAGESIZE"],
            "data": cursor_rows,
        },
    }


def _history_rows(count, *, high_start=100.0):
    return [
        [
            "TQBR",
            "2024-01-03",
            "Сбербанк",
            "SBER",
            high_start + index - 1,
            high_start + index,
            high_start + index,
        ]
        for index in range(count)
    ]


def test_historical_price_supported():
    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _response(_description()),
            _response(
                _history(
                    ["TQBR", "2024-01-03", "Сбербанк", "SBER", 4900.0, 5050.0, 5000.0],
                    ["TQBR", "2024-01-04", "Сбербанк", "SBER", 4950.0, 5100.0, 5080.0],
                )
            ),
        ],
    ):
        status, evidence = verify_historical_price("SBER", 5000.0, "2024-01-03", "2024-01-04")
    assert status == E4_VERIFIED
    assert evidence["observed_max_high"] == 5100.0
    assert evidence["trading_days_count"] == 2
    assert evidence["result"] == "VERIFIED"


def test_historical_price_contradicted():
    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _response(_description()),
            _response(
                _history(
                    ["TQBR", "2024-01-03", "Сбербанк", "SBER", 4700.0, 4800.0, 4750.0],
                )
            ),
        ],
    ):
        status, evidence = verify_historical_price("SBER", 5000.0, "2024-01-03", "2024-01-04")
    assert status == E4_CONTRADICTED
    assert evidence["observed_max_high"] == 4800.0
    assert evidence["reason"] == "historical_max_below_claimed"


def test_ticker_not_yet_existed():
    with patch(
        "urllib.request.urlopen",
        return_value=_response(_description(issue_date="2007-07-20")),
    ) as mocked:
        status, evidence = verify_historical_price("SBER", 5000.0, "2000-01-01", "2001-01-01")
    assert status == E4_INCONCLUSIVE
    assert evidence["reason"] == "ticker_not_yet_existed"
    mocked.assert_called_once()


def test_no_data_in_range():
    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _response(_description()),
            _response(_history()),
        ],
    ):
        status, evidence = verify_historical_price("SBER", 5000.0, "2024-01-01", "2024-01-31")
    assert status == E4_INCONCLUSIVE
    assert evidence["reason"] == "no_data_in_range"
    assert evidence["trading_days_count"] == 0


def test_ticker_reassigned():
    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _response(_description()),
            _response(
                _history(
                    ["TQBR", "2024-01-03", "Сбербанк", "SBER", 4700.0, 4800.0, 4750.0],
                    ["TQBR", "2024-01-04", "Другое общество", "SBER", 4700.0, 4800.0, 4750.0],
                )
            ),
        ],
    ):
        status, evidence = verify_historical_price("SBER", 5000.0, "2024-01-03", "2024-01-04")
    assert status == E4_INCONCLUSIVE
    assert evidence["reason"] == "ticker_reassigned"



def test_pagination_fetches_all_pages():
    first = _history(*_history_rows(100), cursor=(0, 250, 100))
    second = _history(*_history_rows(100, high_start=200), cursor=(100, 250, 100))
    third = _history(*_history_rows(50, high_start=500), cursor=(200, 250, 100))
    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _response(_description()),
            _response(first),
            _response(second),
            _response(third),
        ],
    ):
        status, evidence = verify_historical_price(
            "SBER", 500.0, "2024-01-01", "2024-12-31"
        )
    assert status == E4_VERIFIED
    assert evidence["pages_fetched"] == 3
    assert evidence["trading_days_count"] == 250
    assert evidence["total_rows"] == 250
    assert evidence["observed_max_high"] == 549.0
    assert evidence["expected_trading_days_approx"] == 250


def test_pagination_stalled_returns_inconclusive():
    first = _history(*_history_rows(100), cursor=(0, 250, 100))
    stalled = _history(*_history_rows(100), cursor=(0, 250, 100))
    with patch(
        "urllib.request.urlopen",
        side_effect=[_response(_description()), _response(first), _response(stalled)],
    ):
        status, evidence = verify_historical_price(
            "SBER", 500.0, "2024-01-01", "2024-12-31"
        )
    assert status == E4_INCONCLUSIVE
    assert evidence["reason"] == "pagination_stalled"
    assert evidence["pages_fetched"] == 2


def test_incomplete_history_fetch():
    first = _history(*_history_rows(100), cursor=(0, 3000, 100))
    second = _history(*_history_rows(100), cursor=[])
    with patch(
        "urllib.request.urlopen",
        side_effect=[_response(_description()), _response(first), _response(second)],
    ):
        status, evidence = verify_historical_price(
            "SBER", 5000.0, "2013-01-01", "2026-10-28"
        )
    assert status == E4_INCONCLUSIVE
    assert evidence["reason"] == "incomplete_history_fetch"
    assert evidence["expected_approx"] == evidence["expected_trading_days_approx"]
    assert evidence["received"] == 200
    assert evidence["total_rows"] == 3000
