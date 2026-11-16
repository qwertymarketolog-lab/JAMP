from __future__ import annotations

from jamp.runtime.claim_extractor import extract_claims


def test_extracts_each_ticker_value_pair_from_multi_claim_sentence() -> None:
    claims = extract_claims("SBER 300, а BTC 60000.", trace_id="multi")

    assert [(claim.text, claim.ticker, claim.claim_type, claim.cited_value) for claim in claims] == [
        ("SBER 300", "SBER", "price", 300.0),
        ("BTC 60000", "BTC", "price", 60000.0),
    ]
    assert [claim.id for claim in claims] == ["multi_c1", "multi_c2"]


def test_splits_semicolon_and_conjunction_only_before_ticker_value_pair() -> None:
    claims = extract_claims("SBER 300; BTC 60000 и цена выросла.")

    assert [claim.text for claim in claims] == [
        "SBER 300",
        "BTC 60000 и цена выросла",
    ]


def test_historical_year_is_skipped_without_discarding_later_price() -> None:
    claim = extract_claims("В 2025 году SBER стоил 300.")[0]

    assert claim.text == "В 2025 году SBER стоил 300."
    assert claim.ticker == "SBER"
    assert claim.claim_type == "price"
    assert claim.cited_value == 300.0
    assert claim.currency is None


def test_historical_year_with_abbreviated_suffix_keeps_price() -> None:
    claim = extract_claims("В 2025 г. SBER стоил 300.")[0]

    assert claim.cited_value == 300.0
    assert claim.ticker == "SBER"
    assert claim.claim_type == "price"


def test_ticker_number_pair_without_currency_is_price_with_unknown_currency() -> None:
    claim = extract_claims("SBER 300")[0]

    assert claim.claim_type == "price"
    assert claim.ticker == "SBER"
    assert claim.cited_value == 300.0
    assert claim.currency is None
