from __future__ import annotations

from pathlib import Path

import pytest

from experiments.crypto_audit import run_crypto_audit as audit

ROOT = Path(__file__).resolve().parents[1]


def _mock_response(case: dict) -> dict:
    case_id = case["id"]
    if case.get("acceptance_rule", {}).get("kind") == "explicit_refusal":
        status, aggregate_status, reason, e4_status = (
            "REFUSE", "CONTRADICTED", "E4_CANNOT_VERIFY_EXISTENCE", "CONTRADICTED"
        )
        evidence = {
            "claim_type": "existence",
            "coin_id": case["e4_claim"]["coin_id"],
            "reason": "COIN_NOT_FOUND",
        }
        claims = [{
            "source": "E4_COINGECKO", "status": e4_status,
            "critical": True, "evidence": evidence,
        }]
    elif case_id == "C04":
        status, aggregate_status, reason, e4_status = "EXECUTE", "VERIFIED", None, "VERIFIED"
        evidence = {
            "claim_type": "market_cap", "claimed_value": 50000000000,
            "observed_value": 60000000000, "predicate_satisfied": True,
            "comparison": "greater_than",
        }
        claims = [{"source": "E4_COINGECKO", "status": e4_status, "evidence": evidence}]
    elif case_id == "C05":
        status, aggregate_status, reason, e4_status = "EXECUTE", "VERIFIED", None, "VERIFIED"
        evidence = {
            "claim_type": "price", "claimed_value": 1.0, "observed_value": 1.001,
            "relative_delta_pct": 0.1,
        }
        claims = [{"source": "E4_COINGECKO", "status": e4_status, "evidence": evidence}]
    elif case["expected_behavior"] == "PARTIAL":
        status, aggregate_status, reason, e4_status = "EXECUTE", "PARTIAL", None, "INCONCLUSIVE"
        evidence = {"claim_type": case["e4_claim"]["claim_type"], "reason": "OUTSIDE_E4_SCOPE"}
        claims = [{"source": "E4_COINGECKO", "status": e4_status, "evidence": evidence}]
    else:
        status, aggregate_status, reason, e4_status = "EXECUTE", "VERIFIED", None, "VERIFIED"
        evidence = {"claim_type": case["e4_claim"]["claim_type"], "coin_id": "bitcoin"}
        claims = [{"source": "E4_COINGECKO", "status": e4_status, "evidence": evidence}]
    return {
        "status": status, "execution_status": status, "reason": reason,
        "trace_id": f"trace_{case_id}", "evidence_status": "VERIFIED",
        "aggregate_status": aggregate_status,
        "output": {"content": f"Full model response for {case_id}: " + "model text " * 25},
        "claims": claims, "verdict": {"trace_id": f"trace_{case_id}"},
    }


@pytest.mark.parametrize("case_id", [f"C{i:02d}" for i in range(1, 13)])
def test_crypto_case_acceptance_with_mocked_http(monkeypatch, tmp_path, case_id):
    cases = {case["id"]: case for case in audit._load_cases()}
    case = cases[case_id]
    response = _mock_response(case)

    def fake_http_json(url, *, payload=None, timeout=audit.REQUEST_TIMEOUT):
        if url.endswith("/v1/execute"):
            return 200, response
        if url.endswith("/v1/verify-verdict"):
            return 200, {"valid": True}
        if "/v1/provenance/" in url:
            return 200, {"trace_id": response["trace_id"]}
        raise AssertionError(f"Unexpected mocked URL: {url}")

    monkeypatch.setattr(audit, "_http_json", fake_http_json)
    record = audit._check_case(case, "http://jamp.test", tmp_path / "provenance.jsonl")
    assert record["result"] == "PASSED", record.get("reason")
    assert record["model_response"].startswith(f"Full model response for {case_id}: ")
    assert record["e4_status"] == response["claims"][0]["status"]


def test_runner_delegates_acceptance_and_does_not_duplicate_rules():
    source = (ROOT / "experiments" / "crypto_audit" / "run_crypto_audit.py").read_text()
    assert "from jamp.stock_audit_acceptance import evaluate_acceptance" in source
    assert "expected ==" not in source
    assert "def evaluate_acceptance" not in source


def test_case_catalog_has_exact_ids_and_data_driven_fake_token_rules():
    cases = audit._load_cases()
    assert [case["id"] for case in cases] == [f"C{i:02d}" for i in range(1, 13)]
    for case_id in ("C07", "C10"):
        case = next(item for item in cases if item["id"] == case_id)
        assert case["acceptance_rule"] == {
            "kind": "explicit_refusal",
            "required_status": "REFUSE",
            "required_evidence_status": "VERIFIED",
            "required_response_reason": "E4_CANNOT_VERIFY_EXISTENCE",
        }


def test_markdown_report_preserves_complete_model_response():
    response = "complete response " * 300
    markdown = audit._build_markdown_report(
        {"result": "HOLD/FAILED", "cases": [{
            "id": "C01", "question": "question", "result": "FAILED", "status": "EXECUTE",
            "model_response": response, "e4_status": "VERIFIED", "e4_details": {},
            "reason": "expected failure",
        }]},
        run_id="123", sha="abc", generated_at_utc="2026-10-27T00:00:00+00:00",
    )
    assert response in markdown
