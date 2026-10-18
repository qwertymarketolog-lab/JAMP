from __future__ import annotations

from pathlib import Path

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


def test_snapshot_filters_free_models_and_marks_stem_match_unverified(tmp_path):
    payload = {
        "data": [
            model("provider/nemotron-3-super-120b-a12b:free", "0", "0"),
            model("provider/paid-model", "0.1", "0"),
            {"id": "provider/missing-price", "pricing": {"prompt": "0"}},
            model("provider/exact-match:free", 0, 0),
            model("openrouter/free", "0", "0"),
        ]
    }
    snapshot = catalog.build_snapshot(
        payload,
        [
            "am/nemotron-3-super-120b-a12b",
            "provider/exact-match:free",
        ],
        "TEST_CROSSWALK",
        retrieved_at="2026-10-18T00:00:00Z",
        crosswalk_path=tmp_path / "crosswalk.csv",
    )

    assert snapshot["source"]["catalog_model_count"] == 5
    assert snapshot["source"]["zero_price_entry_count"] == 3
    assert snapshot["source"]["zero_price_model_count"] == 2
    assert snapshot["source"]["free_router_entry_count"] == 1
    assert snapshot["free_router"]["present"] is True
    assert [row["id"] for row in snapshot["models"]] == [
        "provider/exact-match:free",
        "provider/nemotron-3-super-120b-a12b:free",
    ]
    assert snapshot["comparison"]["exact_model_id_matches"] == [
        "provider/exact-match:free"
    ]
    assert snapshot["comparison"]["name_stem_candidates"] == [
        {
            "anymodel_model_id": "am/nemotron-3-super-120b-a12b",
            "openrouter_model_ids": ["provider/nemotron-3-super-120b-a12b:free"],
            "status": "NAME_STEM_CANDIDATE_NOT_IDENTITY_PROOF",
        }
    ]
    assert snapshot["qualification"]["jamp_execution_approved"] is False
    assert snapshot["qualification"]["model_quality_verified"] is False
    assert snapshot["comparison"]["crosswalk_path"] == str(tmp_path / "crosswalk.csv")


def test_snapshot_rejects_duplicate_model_ids():
    payload = {
        "data": [
            model("provider/same", "0", "0"),
            model("provider/same", "0", "0"),
        ]
    }
    with pytest.raises(RuntimeError, match="duplicate model IDs"):
        catalog.build_snapshot(payload, [], "NOT_FOUND")


def test_snapshot_rejects_malformed_rows():
    with pytest.raises(RuntimeError, match="malformed model row"):
        catalog.build_snapshot({"data": [{"name": "missing id"}]}, [], "NOT_FOUND")


def test_crosswalk_requires_87_unique_ids(tmp_path):
    path = tmp_path / "crosswalk.csv"
    path.write_text(
        "ordinal,model_id,in_36,in_17,stage\n"
        + "".join(f'{index},"model/{index}",false,false,"87-only"\n' for index in range(1, 88)),
        encoding="utf-8",
    )
    ids, status = catalog.read_crosswalk(path)
    assert len(ids) == 87
    assert status == "VALID_87_MODEL_CROSSWALK"


def test_crosswalk_wrong_cardinality_is_not_treated_as_valid(tmp_path):
    path = tmp_path / "crosswalk.csv"
    path.write_text(
        'ordinal,model_id,in_36,in_17,stage\n1,"model/one",false,false,"87-only"\n',
        encoding="utf-8",
    )
    ids, status = catalog.read_crosswalk(path)
    assert ids == ["model/one"]
    assert status == "INCONCLUSIVE_CARDINALITY"
