from __future__ import annotations

import re

import pytest

from jamp.runtime.claim_extractor import Claim, extract_claims


def test_extracts_price_after_year_and_ruble_marker() -> None:
    claim = extract_claims("В 2025 году SBER достиг 5000₽")[0]

    assert claim.cited_value == 5000.0
    assert claim.currency == "RUB"
    assert claim.ticker == "SBER"
    assert claim.claim_type == "price"


def test_extracts_price_not_percentage() -> None:
    claim = extract_claims("SBER вырос на 10% и цена достигла 5000₽")[0]

    assert claim.cited_value == 5000.0
    assert claim.currency == "RUB"


def test_extracts_usd_currency() -> None:
    claim = extract_claims("Цена BTC составляет $50000")[0]

    assert claim.cited_value == 50000.0
    assert claim.currency == "USD"


def test_price_without_currency_keeps_currency_unknown() -> None:
    claim = extract_claims("Цена SBER составляет 5000")[0]

    assert claim.cited_value == 5000.0
    assert claim.currency is None


def test_entity_existence_is_not_a_market_instrument() -> None:
    claim = extract_claims("FakeTech объявила IPO")[0]

    assert claim.claim_type == "entity_existence"
    assert claim.ticker is None
    assert claim.cited_value is None
    assert claim.currency is None


def test_prediction_takes_precedence_over_causal_marker() -> None:
    claim = extract_claims("SBER вырастет из-за дивидендов")[0]

    assert claim.ticker == "SBER"
    assert claim.claim_type == "prediction"


def test_extracts_citation_url_without_treating_it_as_evidence() -> None:
    claim = extract_claims(
        "Согласно https://iss.moex.com/iss/securities/SBER.json, "
        "SBER=5000"
    )[0]

    assert claim.citation_url == "https://iss.moex.com/iss/securities/SBER.json"
    assert claim.ticker == "SBER"
    assert claim.claim_type == "price"
    assert claim.cited_value == 5000.0


def test_multiple_claims_have_trace_scoped_ids() -> None:
    claims = extract_claims(
        "SBER достиг 5000₽. FakeTech объявила IPO.",
        trace_id="trace-123",
    )

    assert [claim.id for claim in claims] == ["trace-123_c1", "trace-123_c2"]
    assert [claim.claim_type for claim in claims] == ["price", "entity_existence"]


def test_default_ids_are_uuid4_and_unique_across_calls() -> None:
    first = extract_claims("SBER достиг 5000₽")[0].id
    second = extract_claims("SBER достиг 5000₽")[0].id

    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        first,
    )
    assert first != second


def test_empty_input_returns_no_claims() -> None:
    assert extract_claims("") == []
    assert extract_claims("  \\n ") == []


def test_non_string_input_is_rejected() -> None:
    with pytest.raises(TypeError, match="text must be a string"):
        extract_claims(None)  # type: ignore[arg-type]


def test_empty_trace_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="trace_id must be non-empty"):
        extract_claims("SBER достиг 5000₽", trace_id="  ")


def test_claim_dataclass_contains_no_verdict_fields() -> None:
    claim = extract_claims("SBER достиг 5000₽", trace_id="trace")[0]

    assert claim == Claim(
        id="trace_c1",
        text="SBER достиг 5000₽",
        ticker="SBER",
        claim_type="price",
        cited_value=5000.0,
        currency="RUB",
        citation_url=None,
    )
    assert not hasattr(claim, "status")
    assert not hasattr(claim, "source")
    assert not hasattr(claim, "evidence")
