from __future__ import annotations

import pytest

from scripts.research import openrouter_free_catalog as catalog


def model(model_id: str, prompt: object, completion: object) -> dict:
    return {
        "id": model_id,
        "name": model_id,
        "pricing": {"prompt": prompt, "completion": completion},
        "context_length": 8192,
    }


def test_zero_price_requires_explicit_zero_values():
    assert catalog.zero_price("0")
    assert catalog.zero_price(0)
    assert catalog.zero_price("0.000")
    assert not catalog.zero_price(None)
    assert not catalog.zero_price("")
    assert not catalog.zero_price("unknown")
    assert not catalog.zero_price("0.01")
    assert not catalog.zero_price(True)


def test_snapshot_filters_free_models_and_keeps_router_separate():
    payload = {
        "data": [
            model("provider/free-model:free", "0", "0"),
            model("provider/paid-model", "0.1", "0"),
            {"id": "provider/missing-price", "pricing": {"prompt": "0"}},
            model("openrouter/free", "0", "0"),
        ]
    }
    snapshot = catalog.build_snapshot(
        payload,
        retrieved_at="2026-10-18T00:00:00Z",
        endpoint="https://example.test/models",
    )

    assert snapshot["source"]["catalog_model_count"] == 4
    assert snapshot["source"]["zero_price_entry_count"] == 2
    assert snapshot["source"]["zero_price_model_count"] == 1
    assert snapshot["source"]["free_router_entry_count"] == 1
    assert snapshot["source"]["endpoint"] == "https://example.test/models"
    assert [row["id"] for row in snapshot["all_models"]] == [
        "openrouter/free",
        "provider/free-model:free",
        "provider/missing-price",
        "provider/paid-model",
    ]
    assert snapshot["free_router"]["present"] is True
    assert [row["id"] for row in snapshot["models"]] == ["provider/free-model:free"]
    assert snapshot["qualification"]["jamp_execution_approved"] is False
    assert snapshot["qualification"]["model_quality_verified"] is False
    assert snapshot["qualification"]["live_chat_completion_tested"] is False


def test_snapshot_rejects_duplicate_model_ids():
    payload = {
        "data": [
            model("provider/same", "0", "0"),
            model("provider/same", "0", "0"),
        ]
    }
    with pytest.raises(RuntimeError, match="duplicate model IDs"):
        catalog.build_snapshot(payload)


def test_snapshot_rejects_malformed_rows():
    with pytest.raises(RuntimeError, match="malformed model row"):
        catalog.build_snapshot({"data": [{"name": "missing id"}]})
