from __future__ import annotations

import urllib.error
from unittest.mock import patch

from experiments.r18_r22_e2e import run_pipeline as pipeline


def test_extract_price() -> None:
    claim = pipeline.extract_claims("SBER 5000₽")[0]
    assert (claim.ticker, claim.claim_type, claim.cited_value) == ("SBER", "price", 5000.0)


def test_extract_existence() -> None:
    claim = pipeline.extract_claims("FakeTech объявила IPO")[0]
    assert claim.claim_type == "existence"
    assert claim.ticker == "FAKETECH"


def test_extract_prediction() -> None:
    assert pipeline.extract_claims("SBER вырастет")[0].claim_type == "prediction"


def test_extract_causal() -> None:
    assert pipeline.extract_claims("SBER вырос из-за дивидендов")[0].claim_type == "causal"


def test_extract_citation_url() -> None:
    claim = pipeline.extract_claims("SBER подтверждён: https://iss.moex.com/iss/securities")[0]
    assert claim.citation_url == "https://iss.moex.com/iss/securities"


def test_citation_whitelist_moex() -> None:
    with patch.object(pipeline.urllib.request, "urlopen", side_effect=AssertionError("network")):
        assert pipeline.check_citation("https://iss.moex.com/iss/securities") == (True, None)


def test_citation_invalid_url() -> None:
    assert pipeline.check_citation("not-a-url") == (False, "malformed_url")


def test_citation_fake_domain() -> None:
    with patch.object(
        pipeline.urllib.request,
        "urlopen",
        side_effect=urllib.error.URLError("offline"),
    ):
        ok, reason = pipeline.check_citation("https://example.invalid/evidence")
    assert not ok
    assert reason == "URLError"


def test_verdict_mapping() -> None:
    assert pipeline.map_e4_verdict("E4_VERIFIED") == "supported"
    assert pipeline.map_e4_verdict("E4_CONTRADICTED") == "contradicted"
    assert pipeline.map_e4_verdict("E4_OUT_OF_SCOPE") == "ambiguous"
    assert pipeline.map_e4_verdict("E4_INCONCLUSIVE") == "inconclusive"


def test_default_sample_has_four_claims() -> None:
    claims = pipeline.extract_claims(pipeline.DEFAULT_SAMPLE)
    assert len(claims) == 4
    assert any(claim.ticker == "FAKETECH" and claim.claim_type == "existence" for claim in claims)


def test_pipeline_coverage_full() -> None:
    text = "SBER 5000₽. SBER. SBER вырастет. SBER вырос из-за дивидендов."
    with patch.object(
        pipeline,
        "_verify_claim",
        side_effect=[
            ("E4_VERIFIED", {"source": "fixture"}),
            ("E4_CONTRADICTED", {"source": "fixture"}),
        ],
    ):
        report = pipeline.run_pipeline(text)
    assert report["coverage"]["total"] == 4
    assert report["coverage"]["verified"] == 2
    assert report["coverage"]["inconclusive"] == 2
    assert report["coverage"]["verified_ratio"] == 0.5


def test_pipeline_coverage_empty() -> None:
    report = pipeline.run_pipeline("")
    assert report["coverage"]["total"] == 0
    assert report["coverage"]["verified_ratio"] is None


def test_inconclusive_has_reason() -> None:
    report = pipeline.run_pipeline("SBER вырастет. SBER вырос из-за дивидендов.")
    assert all(item["reason"] for item in report["claims"] if item["verdict"] == "inconclusive")


def test_ticker_not_extracted_from_url() -> None:
    text = (
        "Согласно https://iss.moex.com/iss/engines/stock/markets/shares/"
        "boards/TQBR/securities/SBER.json, SBER достиг 5000 рублей."
    )
    claim = pipeline.extract_claims(text)[0]
    assert claim.ticker == "SBER"
    assert claim.claim_type == "historical_price"
    assert claim.cited_value == 5000.0
    assert (
        claim.citation_url
        == "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/SBER.json"
    )


def test_change_percent_not_price() -> None:
    claim = pipeline.extract_claims("VKCO потерял 93% капитализации")[0]
    assert claim.ticker == "VKCO"
    assert claim.claim_type == "change_percent"
    assert claim.cited_value == 93.0
    report = pipeline.run_pipeline("VKCO потерял 93% капитализации")
    result = report["claims"][0]
    assert result["verdict"] == "inconclusive"
    assert result["reason"] == "requires_E5_or_history"


def test_fake_existence_not_found() -> None:
    with patch.object(
        pipeline,
        "_verify_claim",
        return_value=(
            "E4_OUT_OF_SCOPE",
            {"reason": "ticker_not_found", "checked_source": "moex.iss"},
        ),
    ):
        report = pipeline.run_pipeline("FakeTech объявила IPO")
    result = report["claims"][0]
    assert result["claim_type"] == "existence"
    assert result["verdict"] == "not_found"


def test_historical_price_marker() -> None:
    """Past-tense price → historical_price."""
    claims = pipeline.extract_claims("SBER достиг 5000₽.")
    assert len(claims) == 1
    assert claims[0].claim_type == "historical_price"
    assert claims[0].ticker == "SBER"


def test_current_price_no_marker() -> None:
    """Present-tense price → price (регрессия)."""
    claims = pipeline.extract_claims("SBER стоит 5000₽.")
    assert len(claims) == 1
    assert claims[0].claim_type == "price"


def test_historical_price_returns_inconclusive() -> None:
    """historical_price delegates to MOEX history and preserves inconclusive evidence."""
    with patch(
        "jamp.provider.moex_history.verify_historical_price",
        return_value=("INCONCLUSIVE", {"reason": "no_data_in_range"}),
    ):
        report = pipeline.run_pipeline("SBER достиг 5000₽.")
    assert len(report["claims"]) == 1
    claim = report["claims"][0]
    assert claim["claim_type"] == "historical_price"
    assert claim["verdict"] == "inconclusive"
    assert claim["reason"] == "no_data_in_range"
    assert "R19" in claim["r_codes"]


def test_historical_price_supported_via_adapter() -> None:
    with patch(
        "jamp.provider.moex_history.verify_historical_price",
        return_value=("VERIFIED", {"reason": None, "observed_max_high": 5100.0}),
    ):
        report = pipeline.run_pipeline("SBER достиг 5000₽.")
    assert report["claims"][0]["verdict"] == "supported"


def test_historical_price_contradicted_via_adapter() -> None:
    with patch(
        "jamp.provider.moex_history.verify_historical_price",
        return_value=("CONTRADICTED", {"reason": "historical_max_below_claimed"}),
    ):
        report = pipeline.run_pipeline("SBER достиг 5000₽.")
    assert report["claims"][0]["verdict"] == "contradicted"


def test_coverage_verified_and_confirmed_separate() -> None:
    """not_found is verified as a source answer, but not confirmed as claim truth."""
    with patch.object(
        pipeline,
        "_verify_claim",
        return_value=(
            "E4_OUT_OF_SCOPE",
            {"reason": "ticker_not_found", "checked_source": "moex.iss"},
        ),
    ):
        report = pipeline.run_pipeline("FakeTech объявила IPO.")

    cov = report["coverage"]
    assert cov["not_found"] == 1
    assert cov["verified"] == 1
    assert cov["confirmed"] == 0
    assert cov["verified_ratio"] == 1.0
    assert cov["confirmed_ratio"] == 0.0
    assert cov["definition"] == {
        "verified": "supported + contradicted + not_found",
        "confirmed": "supported + contradicted",
        "verified_meaning": "source returned a conclusive answer (including verified absence)",
        "confirmed_meaning": "claim proven true or false",
    }


def test_coverage_empty_returns_none() -> None:
    """An empty report has undefined ratios, not zero ratios."""
    report = pipeline.run_pipeline("")
    cov = report["coverage"]
    assert cov["total"] == 0
    assert cov["verified_ratio"] is None
    assert cov["confirmed_ratio"] is None


def test_e5_disabled_by_default(monkeypatch):
    monkeypatch.delenv("JAMP_E5_ENABLED", raising=False)
    report = pipeline.run_pipeline("SBER вырастет из-за дивидендов.")
    assert report["claims"][0]["verdict"] == "inconclusive"
    assert report["claims"][0]["reason"] == "requires_E5_search"


def test_e5_enabled_prediction_calls_search(monkeypatch):
    monkeypatch.setenv("JAMP_E5_ENABLED", "true")
    with patch(
        "experiments.r18_r22_e2e.run_pipeline.verify_with_search",
        return_value=("E5_VERIFIED", {"checked_source": "tavily"}),
    ):
        report = pipeline.run_pipeline("SBER вырастет из-за дивидендов.")
    assert report["claims"][0]["verdict"] == "supported"
    assert report["claims"][0]["evidence"]["checked_source"] == "tavily"


def test_e5_enabled_causal_contradicted(monkeypatch):
    monkeypatch.setenv("JAMP_E5_ENABLED", "true")
    with patch(
        "experiments.r18_r22_e2e.run_pipeline.verify_with_search",
        return_value=("E5_CONTRADICTED", {"reason": "conflicting_sources"}),
    ):
        report = pipeline.run_pipeline("SBER вырос из-за дивидендов.")
    assert report["claims"][0]["verdict"] == "contradicted"


def test_e5_does_not_override_e4_historical(monkeypatch):
    monkeypatch.setenv("JAMP_E5_ENABLED", "true")
    with (
        patch(
            "experiments.r18_r22_e2e.run_pipeline.verify_with_search",
        ) as mock_e5,
        patch(
            "jamp.provider.moex_history.verify_historical_price",
            return_value=("CONTRADICTED", {"reason": "historical_max_below_claimed"}),
        ),
    ):
        report = pipeline.run_pipeline("SBER достиг 5000₽.")
    mock_e5.assert_not_called()
    assert report["claims"][0]["verdict"] == "contradicted"


def test_e5_inconclusive_preserves_reason(monkeypatch):
    monkeypatch.setenv("JAMP_E5_ENABLED", "true")
    with patch(
        "experiments.r18_r22_e2e.run_pipeline.verify_with_search",
        return_value=("E5_INCONCLUSIVE", {"reason": "rate_limit"}),
    ):
        report = pipeline.run_pipeline("SBER вырастет из-за дивидендов.")
    assert report["claims"][0]["verdict"] == "inconclusive"
    assert report["claims"][0]["reason"] == "rate_limit"
