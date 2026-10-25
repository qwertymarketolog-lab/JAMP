from __future__ import annotations

from jamp.runtime import qualification


def test_registered_benchmark_qualification_is_returned(monkeypatch):
    monkeypatch.setitem(
        qualification.QUALIFICATION_REGISTRY,
        ("fixture/model-qualified", "search_and_extraction"),
        "QUALIFIED",
    )

    assert (
        qualification.evaluate_model_qualification(
            "fixture/model-qualified", "search_and_extraction"
        )
        == "QUALIFIED"
    )


def test_unknown_model_fails_closed_to_unknown():
    assert (
        qualification.evaluate_model_qualification(
            "unknown/model", "search_and_extraction"
        )
        == "UNKNOWN"
    )


def test_single_successful_financial_audit_does_not_qualify_glm():
    assert (
        qualification.evaluate_model_qualification(
            "z-ai/glm-5.3-flash", "search_and_extraction"
        )
        == "UNKNOWN"
    )


def test_invalid_model_or_task_fails_closed():
    assert qualification.evaluate_model_qualification("", "search_and_extraction") == "UNKNOWN"
    assert qualification.evaluate_model_qualification("fixture/model-qualified", "") == "UNKNOWN"
