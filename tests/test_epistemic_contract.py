from __future__ import annotations

import inspect
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from jamp.provider import coingecko_verify, moex_verify
from jamp.runtime.verdict import JampVerdict, aggregate_verdict

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "status_definitions.json"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_status_definitions_document_matches_embedded_json_schema() -> None:
    contract = _contract()
    schema = contract["json_schema"]
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        {key: value for key, value in contract.items() if key != "json_schema"}
    )


def test_signed_claim_status_vocabulary_matches_runtime_parser() -> None:
    contract = _contract()
    expected = set(contract["claim_level"])
    base = {
        "trace_id": "trace_contract_1",
        "provider_model_id": "provider/model",
        "evidence_hash": "sha256:" + "a" * 64,
        "timestamp": 1_800_000_000.0,
    }
    accepted: set[str] = set()
    for status in ("VERIFIED", "CONTRADICTED", "INCONCLUSIVE", "NOT_A_STATUS"):
        try:
            JampVerdict.from_dict({**base, "status": status})
        except ValueError:
            continue
        accepted.add(status)
    assert accepted == expected


def test_aggregate_status_vocabulary_matches_runtime_behavior() -> None:
    contract = _contract()
    observed = {
        aggregate_verdict([]),
        aggregate_verdict([{"status": "VERIFIED"}]),
        aggregate_verdict([{"status": "CONTRADICTED"}]),
        aggregate_verdict([{"status": "INCONCLUSIVE", "critical": True}]),
        aggregate_verdict([{"status": "INCONCLUSIVE", "critical": False}]),
    }
    assert observed == set(contract["aggregate_level"])


def test_aggregate_precedence_is_explicit_and_deterministic() -> None:
    assert aggregate_verdict(
        [
            {"status": "INCONCLUSIVE", "critical": True},
            {"status": "CONTRADICTED", "critical": False},
        ]
    ) == "CONTRADICTED"
    assert aggregate_verdict([{"status": "INCONCLUSIVE", "critical": True}]) == "INCONCLUSIVE"
    assert aggregate_verdict([{"status": "INCONCLUSIVE", "critical": False}]) == "PARTIAL"
    assert aggregate_verdict([]) == "PARTIAL"


def test_provider_e4_vocabulary_matches_both_adapters() -> None:
    expected = set(_contract()["provider_e4"])
    moex = {
        moex_verify.E4_VERIFIED,
        moex_verify.E4_CONTRADICTED,
        moex_verify.E4_OUT_OF_SCOPE,
        moex_verify.E4_INCONCLUSIVE,
    }
    coingecko = {
        coingecko_verify.E4_VERIFIED,
        coingecko_verify.E4_CONTRADICTED,
        coingecko_verify.E4_OUT_OF_SCOPE,
        coingecko_verify.E4_INCONCLUSIVE,
    }
    assert moex == expected
    assert coingecko == expected


def test_persisted_dashboard_status_vocabulary_matches_api_allowlist() -> None:
    import ast

    source = (ROOT / "src" / "jamp" / "api" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    actual: set[str] | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "list_verdicts":
            for child in ast.walk(node):
                if isinstance(child, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "allowed_statuses"
                    for target in child.targets
                ):
                    actual = set(ast.literal_eval(child.value))
                    break
    assert actual is not None, "list_verdicts allowed_statuses definition not found"
    assert actual == set(_contract()["persisted_verdict_level"])


def test_source_specific_tolerance_defaults_match_runtime() -> None:
    contract = _contract()
    moex_default = inspect.signature(moex_verify._verify_claim_with_moex).parameters[
        "price_tolerance"
    ].default
    assert moex_default == contract["tolerance_defaults"]["MOEX_ISS"]["price"]["value"]
    actual_coingecko_thresholds = coingecko_verify._DEFAULT_THRESHOLDS
    expected_coingecko_thresholds = {
        key: value["value"]
        for key, value in contract["tolerance_defaults"]["COINGECKO"].items()
    }
    assert actual_coingecko_thresholds == expected_coingecko_thresholds


def test_persisted_labels_are_explicitly_not_claimed_as_runtime_mappings() -> None:
    persisted = _contract()["persisted_verdict_level"]
    assert all(
        item["implementation_status"] == "MAPPING_NOT_ESTABLISHED"
        for item in persisted.values()
    )
