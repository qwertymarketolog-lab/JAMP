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
    assert claim.claim_type == "price"
    assert claim.cited_value == 5000.0
    assert claim.citation_url == "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/SBER.json"


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
