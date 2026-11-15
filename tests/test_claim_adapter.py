from __future__ import annotations

import inspect

import pytest

import jamp.runtime.claim_adapter as claim_adapter
from jamp.runtime.claim_adapter import to_verdict_claim
from jamp.runtime.claim_extractor import extract_claims


EXPECTED_KEYS = {
    "claim_id",
    "type",
    "value",
    "unit",
    "raw_text",
    "citation_url",
    "status",
    "source",
    "evidence",
    "critical",
}


def test_maps_extractor_fields_to_exact_dict_contract() -> None:
    extracted = extract_claims(
        "Согласно https://iss.moex.com/iss/securities/SBER.json, "
        "SBER достиг 5000₽"
    )[0]

    mapped = to_verdict_claim(extracted, "trace-adapter")

    assert set(mapped) == EXPECTED_KEYS
    assert mapped["claim_id"] == f"trace-adapter_{extracted.id}"
    assert mapped["type"] == extracted.claim_type
    assert mapped["value"] == extracted.cited_value
    assert mapped["unit"] == extracted.currency
    assert mapped["raw_text"] == extracted.text
    assert mapped["citation_url"] == extracted.citation_url


def test_status_is_none_after_mapping() -> None:
    extracted = extract_claims("SBER достиг 5000₽")[0]

    assert to_verdict_claim(extracted, "trace-status")["status"] is None


def test_source_is_none_after_mapping() -> None:
    extracted = extract_claims("SBER достиг 5000₽")[0]

    assert to_verdict_claim(extracted, "trace-source")["source"] is None


def test_evidence_is_none_after_mapping() -> None:
    extracted = extract_claims(
        "Согласно https://iss.moex.com/iss/securities/SBER.json, SBER=5000"
    )[0]
    mapped = to_verdict_claim(extracted, "trace-evidence")

    assert mapped["evidence"] is None
    assert mapped["citation_url"] == extracted.citation_url


def test_citation_url_is_not_evidence() -> None:
    extracted = extract_claims(
        "Согласно https://iss.moex.com/iss/securities/SBER.json, SBER=5000"
    )[0]
    mapped = to_verdict_claim(extracted, "trace-citation")

    assert mapped["citation_url"] == "https://iss.moex.com/iss/securities/SBER.json"
    assert mapped["evidence"] is None


def test_critical_is_none_after_mapping() -> None:
    extracted = extract_claims("SBER достиг 5000₽")[0]

    assert to_verdict_claim(extracted, "trace-critical")["critical"] is None


def test_trace_id_scopes_claim_ids_across_runs() -> None:
    extracted_a = extract_claims("SBER достиг 5000₽")[0]
    extracted_b = extract_claims("SBER достиг 5000₽")[0]

    mapped_a = to_verdict_claim(extracted_a, "run-a")
    mapped_b = to_verdict_claim(extracted_b, "run-b")

    assert mapped_a["claim_id"] == f"run-a_{extracted_a.id}"
    assert mapped_b["claim_id"] == f"run-b_{extracted_b.id}"
    assert mapped_a["claim_id"] != mapped_b["claim_id"]


def test_unknown_currency_is_preserved_as_unknown_unit() -> None:
    extracted = extract_claims("Цена SBER составляет 5000")[0]

    mapped = to_verdict_claim(extracted, "trace-unknown")

    assert extracted.currency is None
    assert mapped["unit"] == "UNKNOWN"


@pytest.mark.parametrize(
    ("text", "expected_type", "expected_value", "expected_unit"),
    [
        ("В 2025 году SBER достиг 5000₽", "price", 5000.0, "RUB"),
        ("SBER вырос на 10% и цена достигла 5000₽", "price", 5000.0, "RUB"),
        ("FakeTech объявила IPO", "entity_existence", None, "UNKNOWN"),
        ("Цена BTC составляет $50000", "price", 50000.0, "USD"),
        ("Цена SBER составляет 5000", "price", 5000.0, "UNKNOWN"),
    ],
)
def test_round_trip_five_extractor_examples(
    text: str,
    expected_type: str,
    expected_value: float | None,
    expected_unit: str,
) -> None:
    extracted = extract_claims(text)[0]

    mapped = to_verdict_claim(extracted, "trace-round-trip")

    assert set(mapped) == EXPECTED_KEYS
    assert mapped["claim_id"] == f"trace-round-trip_{extracted.id}"
    assert mapped["type"] == expected_type
    assert mapped["value"] == expected_value
    assert mapped["unit"] == expected_unit
    assert mapped["raw_text"] == text
    assert mapped["citation_url"] is None
    assert mapped["status"] is None
    assert mapped["source"] is None
    assert mapped["evidence"] is None
    assert mapped["critical"] is None


def test_adapter_defines_no_claim_or_verdict_class() -> None:
    defined_classes = [
        name
        for name, member in inspect.getmembers(claim_adapter, inspect.isclass)
        if member.__module__ == claim_adapter.__name__
    ]

    assert "Claim" not in defined_classes
    assert "Verdict" not in defined_classes
    assert "VerdictClaim" not in defined_classes
