from __future__ import annotations

import pytest

from jamp.runtime.claim_extractor import Claim, extract_claims


def test_extracts_price_claim_with_ruble_value() -> None:
    claims = extract_claims("SBER достиг 5000₽")

    assert len(claims) == 1
    assert claims[0] == Claim(
        id="c1",
        text="SBER достиг 5000₽",
        ticker="SBER",
        claim_type="price",
        cited_value=5000.0,
        citation_url=None,
    )


def test_extracts_company_existence_claim() -> None:
    claims = extract_claims("FakeTech объявила IPO")

    assert len(claims) == 1
    assert claims[0].ticker == "FAKETECH"
    assert claims[0].claim_type == "existence"
    assert claims[0].cited_value is None


def test_prediction_takes_precedence_over_causal_marker() -> None:
    claims = extract_claims("SBER вырастет из-за дивидендов")

    assert len(claims) == 1
    assert claims[0].ticker == "SBER"
    assert claims[0].claim_type == "prediction"
    # The causal signal is preserved verbatim; the Claim contract has no
    # separate cause field in v0.
    assert "из-за дивидендов" in claims[0].text


def test_extracts_citation_url_and_price() -> None:
    claims = extract_claims(
        "Согласно https://iss.moex.com/iss/securities/SBER.json, SBER=5000"
    )

    assert len(claims) == 1
    assert claims[0].citation_url == "https://iss.moex.com/iss/securities/SBER.json"
    assert claims[0].ticker == "SBER"
    assert claims[0].claim_type == "price"
    assert claims[0].cited_value == 5000.0


def test_extracts_multiple_claims_with_stable_sequential_ids() -> None:
    claims = extract_claims("SBER достиг 5000₽. FakeTech объявила IPO.")

    assert [claim.id for claim in claims] == ["c1", "c2"]
    assert [claim.claim_type for claim in claims] == ["price", "existence"]


def test_empty_input_returns_no_claims() -> None:
    assert extract_claims("") == []
    assert extract_claims("  \n ") == []


def test_non_string_input_is_rejected() -> None:
    with pytest.raises(TypeError, match="text must be a string"):
        extract_claims(None)  # type: ignore[arg-type]
