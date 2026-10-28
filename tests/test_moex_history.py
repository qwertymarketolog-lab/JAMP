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


def _history(*rows):
    return {
        "history": {
            "columns": ["BOARDID", "TRADEDATE", "SHORTNAME", "SECID", "LOW", "HIGH", "CLOSE"],
            "data": list(rows),
        }
    }


def test_historical_price_supported():
    with patch("urllib.request.urlopen", side_effect=[
        _response(_description()),
        _response(_history(
            ["TQBR", "2024-01-03", "Сбербанк", "SBER", 4900.0, 5050.0, 5000.0],
            ["TQBR", "2024-01-04", "Сбербанк", "SBER", 4950.0, 5100.0, 5080.0],
        )),
    ]):
        status, evidence = verify_historical_price("SBER", 5000.0, "2024-01-01", "2024-01-31")
    assert status == E4_VERIFIED
    assert evidence["observed_max_high"] == 5100.0
    assert evidence["trading_days_count"] == 2
    assert evidence["result"] == "VERIFIED"


def test_historical_price_contradicted():
    with patch("urllib.request.urlopen", side_effect=[
        _response(_description()),
        _response(_history(
            ["TQBR", "2024-01-03", "Сбербанк", "SBER", 4700.0, 4800.0, 4750.0],
        )),
    ]):
        status, evidence = verify_historical_price("SBER", 5000.0, "2024-01-01", "2024-01-31")
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
    with patch("urllib.request.urlopen", side_effect=[
        _response(_description()),
        _response(_history()),
    ]):
        status, evidence = verify_historical_price("SBER", 5000.0, "2024-01-01", "2024-01-31")
    assert status == E4_INCONCLUSIVE
    assert evidence["reason"] == "no_data_in_range"
    assert evidence["trading_days_count"] == 0


def test_ticker_reassigned():
    with patch("urllib.request.urlopen", side_effect=[
        _response(_description()),
        _response(_history(
            ["TQBR", "2024-01-03", "Сбербанк", "SBER", 4700.0, 4800.0, 4750.0],
            ["TQBR", "2024-01-04", "Другое общество", "SBER", 4700.0, 4800.0, 4750.0],
        )),
    ]):
        status, evidence = verify_historical_price("SBER", 5000.0, "2024-01-01", "2024-01-31")
    assert status == E4_INCONCLUSIVE
    assert evidence["reason"] == "ticker_reassigned"
