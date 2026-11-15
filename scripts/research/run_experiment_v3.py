#!/usr/bin/env python3
"""Offline/live harness for direct E4 claim verification v3."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

MOEX_SECURITIES = json.dumps({
    "securities": {
        "columns": ["secid", "shortname"],
        "data": [["SBER", "Sberbank"]],
    }
}, separators=(",", ":")).encode()
MOEX_MARKETDATA = json.dumps({
    "marketdata": {
        "columns": ["SECID", "LAST", "BOARDID", "TRADEDATE"],
        "data": [["SBER", 299.26, "TQBR", "2026-11-15"]],
    }
}, separators=(",", ":")).encode()
COINGECKO_PRICE = b'{"bitcoin":{"usd":64754.0}}'


class FixtureResponse:
    status = 200

    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _size: int = -1) -> bytes:
        return self.body


def fixture_open(request, timeout=5):
    url = request.full_url if hasattr(request, "full_url") else str(request)
    if "iss.moex.com/iss/securities.json" in url:
        return FixtureResponse(MOEX_SECURITIES)
    if "iss.moex.com/iss/engines/stock/markets/shares/securities/SBER.json" in url:
        return FixtureResponse(MOEX_MARKETDATA)
    if "api.coingecko.com/api/v3/simple/price" in url and "ids=bitcoin" in url:
        return FixtureResponse(COINGECKO_PRICE)
    raise AssertionError(f"unlisted mock HTTP request: {url}; timeout={timeout}")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--mock", dest="mode", action="store_const", const="mock")
    mode_group.add_argument("--live", dest="mode", action="store_const", const="live")
    parser.set_defaults(mode="mock")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=pathlib.Path("artifacts/research/experiment_v3"),
    )
    args = parser.parse_args()
    if args.mode == "live" and not args.confirm_live:
        parser.error("--live requires --confirm-live")

    import os
    os.environ.setdefault("JAMP_ENV", "test")
    os.environ.setdefault("JAMP_SIGNING_KEY", "experiment-v3-offline-key")
    os.environ.setdefault("JAMP_API_KEY_HASH_SECRET", "experiment-v3-auth-secret")

    from fastapi.testclient import TestClient
    from jamp.api import create_app
    from jamp.api.auth import require_api_key

    app = create_app()
    app.dependency_overrides[require_api_key] = lambda: {"org_id": "experiment-v3"}
    client = TestClient(app)
    cases = [
        {"id": "exact_match", "text": "Цена SBER 299.26 RUB", "expected_mock": "VERIFIED"},
        {"id": "strong_divergence", "text": "Цена SBER 5000 RUB", "expected_mock": "CONTRADICTED"},
        {"id": "missing_currency", "text": "Цена SBER 299.26", "expected_mock": "INCONCLUSIVE"},
    ]
    original_urlopen = urllib.request.urlopen
    if args.mode == "mock":
        urllib.request.urlopen = fixture_open
    results = []
    try:
        for case in cases:
            response = client.post(
                "/v1/verify_claim",
                json={"text": case["text"], "tolerance_pct": 1.0},
            )
            body = response.json()
            item = {"case_id": case["id"], "http_status": response.status_code, **body}
            if response.status_code != 200:
                raise RuntimeError(f"{case['id']}: HTTP {response.status_code}")
            if args.mode == "mock" and body.get("verdict") != case["expected_mock"]:
                raise AssertionError(
                    f"{case['id']}: expected {case['expected_mock']}, got {body.get('verdict')}"
                )
            if case["id"] == "missing_currency" and body.get("verdict") != "INCONCLUSIVE":
                raise AssertionError("missing currency must fail closed")
            for evidence in body.get("raw_evidence", []):
                raw = base64.b64decode(evidence["raw_body_base64"], validate=True)
                if hashlib.sha256(raw).hexdigest() != evidence["sha256_body"]:
                    raise AssertionError("RAW evidence hash mismatch")
            results.append(item)
    finally:
        if args.mode == "mock":
            urllib.request.urlopen = original_urlopen

    output = {
        "schema": "jamp.experiment-v3-result.v1",
        "mode": args.mode.upper(),
        "status": "OBSERVED",
        "e2_invoked": False,
        "cases": results,
        "note": "Mock outcomes validate logic only; live outcomes are data-dependent.",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / "experiment_v3_result.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"mode": output["mode"], "status": output["status"], "output": str(target)},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
