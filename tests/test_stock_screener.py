from __future__ import annotations

import pytest

from experiments.stock_screener import run_screener as screener


def _metadata(shortname: str = "Самолет") -> dict[str, object]:
    return {
        "SECID": "SMLT",
        "SHORTNAME": shortname,
        "ISSUEDATE": "2021-09-15",
        "IS_TRADED": 1,
        "EMITTER_ID": 123,
    }


def _history_rows(
    *,
    count: int = 600,
    shortname: str = "Самолет",
    max_high: float = 5800.0,
    current: float = 340.0,
    volume: float = 2_000_000.0,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(count):
        rows.append(
            {
                "BOARDID": "TQBR",
                "TRADEDATE": f"2024-{(index // 28) % 12 + 1:02d}-{index % 28 + 1:02d}",
                "SHORTNAME": shortname,
                "SECID": "SMLT",
                "HIGH": max_high if index == 0 else max(current, 400.0),
                "CLOSE": current,
                "VALUE": volume,
            }
        )
    # Ensure unique trading days for trading-day-count checks.
    for index, row in enumerate(rows):
        row["TRADEDATE"] = f"day-{index:04d}"
    return rows


def _install_mock(
    monkeypatch: pytest.MonkeyPatch,
    *,
    metadata: dict[str, object] | None = None,
    history: list[dict[str, object]] | None = None,
    current: float | None = 340.0,
) -> None:
    monkeypatch.setattr(screener, "_security_metadata", lambda ticker: metadata or _metadata())
    monkeypatch.setattr(
        screener,
        "_all_history",
        lambda ticker: history if history is not None else _history_rows(),
    )
    monkeypatch.setattr(screener, "_current_price", lambda ticker: current)


def test_screen_ticker_computes_drawdown(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_mock(monkeypatch)
    result = screener.screen_ticker("SMLT")
    assert result["max_high"] == 5800.0
    assert result["drawdown"] == pytest.approx((5800 - 340) / 5800)
    assert result["drawdown"] == pytest.approx(0.941379, abs=0.001)


def test_filter_by_drawdown_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_mock(monkeypatch, history=_history_rows(max_high=500.0, current=350.0), current=350.0)
    result = screener.screen_ticker("SMLT")
    assert result["drawdown"] == pytest.approx(0.30)
    assert result["verdict"] == "FAIL"


def test_filter_low_liquidity(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_mock(monkeypatch, history=_history_rows(volume=100_000.0))
    result = screener.screen_ticker("SMLT")
    assert result["verdict"] == "SKIP_LIQUIDITY"
    assert "low_liquidity" in result["flags"]


def test_skip_delisted(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_mock(monkeypatch, current=None)
    result = screener.screen_ticker("SMLT")
    assert result["verdict"] == "SKIP_DELISTED"


def test_skip_ticker_reassigned(monkeypatch: pytest.MonkeyPatch) -> None:
    history = _history_rows(shortname="Другое общество")
    _install_mock(monkeypatch, history=history)
    result = screener.screen_ticker("SMLT")
    assert result["verdict"] == "SKIP_REASSIGNED"


def test_skip_insufficient_history(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_mock(monkeypatch, history=_history_rows(count=50))
    result = screener.screen_ticker("SMLT")
    assert result["verdict"] == "SKIP_INSUFFICIENT_HISTORY"


def test_screen_returns_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    results = [
        {"ticker": "P1", "verdict": "PASS"},
        {"ticker": "P2", "verdict": "PASS"},
        {"ticker": "P3", "verdict": "PASS"},
        {"ticker": "P4", "verdict": "PASS"},
        {"ticker": "P5", "verdict": "PASS"},
        {"ticker": "S1", "verdict": "SKIP_DELISTED"},
        {"ticker": "S2", "verdict": "SKIP_LIQUIDITY"},
        {"ticker": "S3", "verdict": "SKIP_REASSIGNED"},
        {"ticker": "F1", "verdict": "FAIL"},
        {"ticker": "F2", "verdict": "FAIL"},
    ]
    monkeypatch.setattr(screener, "screen_ticker", lambda ticker: results.pop(0))
    report = screener.screen([f"T{i}" for i in range(10)])
    assert report["coverage"] == {"pass": 5, "skip": 3, "fail": 2, "total": 10}


def test_empty_list_returns_null_coverage() -> None:
    report = screener.screen([])
    assert report["tickers"] == []
    assert report["coverage"] is None


def test_no_false_pass_on_incomplete_data(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(ticker: str) -> dict[str, object]:
        raise OSError("simulated source failure")

    monkeypatch.setattr(screener, "_security_metadata", fail)
    result = screener.screen_ticker("SMLT")
    assert result["verdict"] == "FAIL"
    assert result["reason"].startswith("MOEX_DATA_ERROR")


def _payload(table_name: str, columns: list[str], data: list[list[object]]) -> dict[str, object]:
    return {table_name: {"columns": columns, "data": data}}


def test_max_high_is_actual_max_not_first_page(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(screener, "_security_metadata", lambda ticker: _metadata())
    monkeypatch.setattr(screener, "_current_price", lambda ticker: 340.0)
    page1 = _payload(
        "history",
        ["BOARDID", "TRADEDATE", "SHORTNAME", "SECID", "HIGH", "VALUE"],
        [["TQBR", "2024-01-01", "Самолет", "SMLT", 500.0, 2_000_000.0]],
    )
    page1["history.cursor"] = {"columns": ["INDEX", "TOTAL", "PAGESIZE"], "data": [[0, 3, 1]]}
    page2 = _payload(
        "history",
        ["BOARDID", "TRADEDATE", "SHORTNAME", "SECID", "HIGH", "VALUE"],
        [["TQBR", "2024-01-02", "Самолет", "SMLT", 600.0, 2_000_000.0]],
    )
    page2["history.cursor"] = {"columns": ["INDEX", "TOTAL", "PAGESIZE"], "data": [[1, 3, 1]]}
    page3 = _payload(
        "history",
        ["BOARDID", "TRADEDATE", "SHORTNAME", "SECID", "HIGH", "VALUE"],
        [["TQBR", "2024-01-03", "Самолет", "SMLT", 5800.0, 2_000_000.0]],
    )
    page3["history.cursor"] = {"columns": ["INDEX", "TOTAL", "PAGESIZE"], "data": [[2, 3, 1]]}
    payloads = [page1, page2, page3]

    def fake_get_json(url: str, timeout: float = 10.0) -> dict[str, object]:
        assert "history/engines/" in url
        return payloads.pop(0)

    monkeypatch.setattr(screener, "_get_json", fake_get_json)
    result = screener.screen_ticker("SMLT")
    assert result["max_high"] == 5800.0
    assert result["max_date"] == "2024-01-03"


def test_current_price_skips_null_board_row_and_prefers_tqbr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "marketdata": {
            "columns": ["SECID", "BOARDID", "LAST", "TRADEDATE"],
            "data": [
                ["SBER", "TQTF", None, "2026-10-28"],
                ["SBER", "TQBR", 250.0, "2026-10-28"],
                ["SBER", "TQOB", 249.5, "2026-10-28"],
            ],
        }
    }
    monkeypatch.setattr(screener, "_get_json", lambda url: payload)
    assert screener._current_price("SBER") == 250.0
