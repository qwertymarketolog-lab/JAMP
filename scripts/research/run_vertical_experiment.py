"""Offline-only vertical experiment for the JAMP E4 API path.

Provider verifier functions are replaced with deterministic local mocks.
This validates integration behavior, not market truth or general hallucination detection.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from jamp.api.auth import OrganizationContext

from jamp.provider.coingecko_verify import E4_CONTRADICTED as CG_CONTRADICTED
from jamp.provider.coingecko_verify import E4_OUT_OF_SCOPE as CG_OUT_OF_SCOPE
from jamp.provider.coingecko_verify import E4_VERIFIED as CG_VERIFIED
from jamp.provider.moex_verify import E4_CONTRADICTED, E4_OUT_OF_SCOPE, E4_VERIFIED
from jamp.runtime.claim_extractor import extract_claims

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "docs/experiments/jamp_audit_v1/vertical_experiment_v1.json"
DEFAULT_OUTPUT = ROOT / "artifacts/vertical-experiment/vertical_experiment_results.json"


def _mock_moex(calls: list[dict[str, Any]]):
    def verify(ticker: str, claim_type: str, claimed_value: float | int | None):
        calls.append({
            "provider": "MOEX", "ticker": ticker, "claim_type": claim_type,
            "claimed_value": claimed_value,
        })
        if ticker != "SBER":
            return E4_OUT_OF_SCOPE, {
                "reason": "MOCK_TICKER_NOT_IN_CATALOG",
                "ticker": ticker,
                "mock_catalog": ["SBER"],
            }
        if claim_type != "price" or claimed_value is None:
            return "E4_INCONCLUSIVE", {"reason": "MOCK_UNSUPPORTED_CLAIM"}
        observed = 300.0
        relative_delta = abs(float(claimed_value) - observed) / observed
        details = {
            "checked_source": "MOCK_MOEX",
            "ticker": ticker,
            "observed_last": observed,
            "claimed_value": float(claimed_value),
            "relative_delta": relative_delta,
            "tolerance": 0.05,
        }
        if relative_delta > 0.05:
            return E4_CONTRADICTED, {**details, "result": "CONTRADICTED"}
        return E4_VERIFIED, {**details, "result": "VERIFIED"}
    return verify


def _mock_coingecko(calls: list[dict[str, Any]]):
    def verify(coin_id: str, claim_type: str, claimed_value: float | int | None):
        calls.append({
            "provider": "COINGECKO", "coin_id": coin_id, "claim_type": claim_type,
            "claimed_value": claimed_value,
        })
        if coin_id != "bitcoin":
            return CG_OUT_OF_SCOPE, {"reason": "MOCK_COIN_NOT_IN_CATALOG", "coin_id": coin_id}
        if claim_type != "price" or claimed_value is None:
            return "E4_INCONCLUSIVE", {"reason": "MOCK_UNSUPPORTED_CLAIM"}
        observed = 65000.0
        delta_pct = abs(float(claimed_value) - observed) / observed * 100.0
        details = {
            "checked_source": "MOCK_COINGECKO",
            "coin_id": coin_id,
            "observed_value": observed,
            "claimed_value": float(claimed_value),
            "relative_delta_pct": delta_pct,
            "threshold_pct": 10.0,
        }
        if delta_pct > 10.0:
            return CG_CONTRADICTED, {**details, "result": "CONTRADICTED"}
        return CG_VERIFIED, {**details, "result": "VERIFIED"}
    return verify


def run_vertical_experiment(
    dataset_path: str | Path = DEFAULT_DATASET,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    """Run all dataset cases through /v1/execute with provider calls mocked."""
    dataset_file = Path(dataset_path)
    output_file = Path(output_path)
    dataset = json.loads(dataset_file.read_text(encoding="utf-8"))
    cases = dataset.get("cases")
    if not isinstance(cases, list) or len(cases) != 10:
        raise ValueError("Vertical Experiment v1 requires exactly 10 cases")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    app_module = importlib.import_module("jamp.api.app")
    calls: list[dict[str, Any]] = []

    def executor(model: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider": "offline-mock",
            "model": model,
            "provider_response_id": "vertical-experiment-v1",
            "provider_model_id": "offline/vertical-experiment",
            "content": str(payload.get("prompt", "")),
        }

    def generation_verifier(_output: Any):
        return "VERIFIED", {"reason": "OFFLINE_HARNESS_MODEL_STUB"}

    results: list[dict[str, Any]] = []
    with (
        patch.dict(os.environ, {
            "JAMP_SIGNING_KEY": "vertical-experiment-test-key",
            "JAMP_ENV": "test",
        }),
        patch.object(app_module, "verify_generation", generation_verifier),
        patch.object(app_module, "verify_claim_with_moex", _mock_moex(calls)),
        patch.object(app_module, "verify_claim_with_coingecko", _mock_coingecko(calls)),
        tempfile.TemporaryDirectory(prefix="jamp-vertical-experiment-") as runtime_dir,
    ):
        app = app_module.create_app(
            executor=executor,
            audit_storage_path=Path(runtime_dir) / "audit.jsonl",
            telegram_update_db_path=Path(runtime_dir) / "telegram-updates.sqlite",
        )
        app.dependency_overrides[app_module.require_api_key] = lambda: OrganizationContext(
            org_id="vertical-experiment", org_name="Vertical Experiment"
        )
        client = TestClient(app)
        try:
            for case in cases:
                calls.clear()
                response = client.post(
                    "/v1/execute",
                    json={"intent": "search_and_extraction", "prompt": case["text"]},
                )
                if response.status_code != 200:
                    raise RuntimeError(
                        f"{case['id']}: API returned HTTP {response.status_code}: "
                        f"{response.text[:500]}"
                    )
                body = response.json()
                claims = body.get("claims", [])
                if not claims:
                    raise RuntimeError(f"{case['id']}: E4 returned no claims")
                actual_claim = claims[0]
                extracted_candidates = extract_claims(case["text"])
                extracted = extracted_candidates[0] if extracted_candidates else None
                actual_extraction = (
                    {
                        "type": extracted.claim_type,
                        "value": extracted.cited_value,
                        "unit": extracted.currency or "UNKNOWN",
                        "ticker": extracted.ticker,
                    }
                    if extracted is not None
                    else None
                )
                actual_status = actual_claim.get("status", "INCONCLUSIVE")
                results.append({
                    "id": case["id"],
                    "trace_id": body.get("trace_id"),
                    "raw_text": case["text"],
                    "extracted_claim": actual_extraction,
                    "expected_extraction": case["expected_extraction"],
                    "extraction_matches_expected": (
                        actual_extraction == case["expected_extraction"]
                    ),
                    "e4_status": actual_status,
                    "expected_e4_status": case["expected_e4_status"],
                    "verdict_matches_expected": (
                        actual_status == case["expected_e4_status"]
                    ),
                    "reason": actual_claim.get("reason"),
                    "aggregate_verdict": body.get("aggregate_status"),
                    "mock_calls": list(calls),
                })
        finally:
            client.close()

    extraction_failures = [
        item["id"] for item in results if not item["extraction_matches_expected"]
    ]
    verdict_failures = [
        item["id"] for item in results if not item["verdict_matches_expected"]
    ]
    payload = {
        "experiment_id": dataset.get("experiment_id"),
        "provider_mode": "MOCK_ONLY",
        "external_provider_calls": 0,
        "case_count": len(results),
        "extraction_failures": extraction_failures,
        "verdict_failures": verdict_failures,
        "results": results,
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run_vertical_experiment(args.dataset, args.output)
    print(
        "VERTICAL_EXPERIMENT_V1 "
        f"cases={result['case_count']} "
        f"extraction_failures={len(result['extraction_failures'])} "
        f"verdict_failures={len(result['verdict_failures'])} "
        f"provider_mode={result['provider_mode']}"
    )
    return 1 if result["extraction_failures"] or result["verdict_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
