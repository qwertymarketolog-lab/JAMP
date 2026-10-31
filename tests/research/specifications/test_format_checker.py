from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "docs/research/specifications/specification-schema-v0.json"


@FormatChecker.cls_checks("date-time")
def _check_date_time(value: object) -> bool:
    """Validate date-time calendar values with stdlib; no jsonschema[format] extra."""
    if not isinstance(value, str):
        return True  # null is allowed by the schema's type declaration.
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(schema: dict) -> Draft202012Validator:
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _valid_spec(**overrides: object) -> dict:
    specification = {
        "spec_id": "5c9426b4-f92f-5742-a2b4-8a244a411708",
        "spec_version": "1.0.0",
        "hypothesis_ref": "a" * 64,
        "prediction_ref": "b" * 64,
        "criterion_set_ref": "c" * 64,
        "preconditions": [{"kind": "k", "value": 1}],
        "scope": {"in_scope": ["x"], "out_of_scope": ["y"]},
        "evidence_classes": ["raw_webhook_payload"],
        "observation_schema": {"fields": [{"name": "s", "type": "string"}]},
        "frozen_at": None,
        "spec_hash": "d" * 64,
    }
    specification.update(overrides)
    return specification


def test_valid_spec_passes(validator: Draft202012Validator) -> None:
    assert list(validator.iter_errors(_valid_spec())) == []


def test_frozen_at_null_allowed(validator: Draft202012Validator) -> None:
    assert list(validator.iter_errors(_valid_spec(frozen_at=None))) == []


def test_frozen_at_valid_timestamp_passes(validator: Draft202012Validator) -> None:
    assert list(validator.iter_errors(_valid_spec(frozen_at="2026-10-31T12:00:00Z"))) == []


@pytest.mark.parametrize(
    "bad",
    [
        "2026-99-99T25:70:00Z",  # calendar invalid; stdlib datetime must reject.
        "not-a-timestamp",
        "2026-10-31",
    ],
)
def test_frozen_at_invalid_rejected(validator: Draft202012Validator, bad: str) -> None:
    errors = list(validator.iter_errors(_valid_spec(frozen_at=bad)))
    assert errors, f"expected rejection for {bad!r}"


def test_additional_property_rejected(validator: Draft202012Validator) -> None:
    specification = _valid_spec()
    specification["extra_field"] = "x"
    assert list(validator.iter_errors(specification))


@pytest.mark.parametrize(
    "bad_id",
    [
        "spec-1",
        "5c9426b4-f92f-4742-a2b4-8a244a411708",  # version nibble = 4.
        "5c9426b4-f92f-5742-72b4-8a244a411708",  # variant nibble = 7.
        "5c9426b4-f92f-5742-c2b4-8a244a411708",  # variant nibble = c.
    ],
)
def test_spec_id_rejects_non_uuidv5(validator: Draft202012Validator, bad_id: str) -> None:
    errors = list(validator.iter_errors(_valid_spec(spec_id=bad_id)))
    assert errors, f"expected rejection for {bad_id!r}"
