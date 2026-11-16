"""Deterministic browser fixture; it never represents live MOEX data."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="JAMP Playwright E2E fixture")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/ui_verify")
def ui_verify(_payload: dict[str, object]) -> dict[str, object]:
    return {
        "status": "COMPLETE_VERIFICATION",
        "system_warnings": [
            "Deterministic Playwright fixture; no live market source was queried."
        ],
        "provider_errors": [],
        "trace_id": "e2e_fixture_sber_contradicted",
        "verification_mode": "DIRECT_E4_NO_E2",
        "claims": [
            {
                "claim_id": "e2e-sber-price-claim",
                "raw_text": "Цена SBER составляет 5000 рублей.",
                "type": "price",
                "extracted_value": 5000,
                "unit": "RUB",
                "verdict": "CONTRADICTED",
                "reason": (
                    "Deterministic browser fixture: fixture quote is 299.26 RUB."
                ),
                "trace_id": "e2e_fixture_sber_contradicted",
                "evidence": [
                    {
                        "source": (
                            "MOEX ISS — deterministic E2E fixture (not live data)"
                        ),
                        "url": None,
                        "status_code": 200,
                        "body_complete": True,
                        "raw_body_base64": "eyJmaXh0dXJlIjoiSkFNUCBQbGF5d3JpZ2h0IEUyRSIsInNvdXJjZSI6Ik1PRVggSVNTIiwiYWN0dWFsX3ZhbHVlIjoyOTkuMjZ9",
                        "actual_value": 299.26,
                        "timestamp_utc": "2026-11-16T00:00:00Z",
                        "timestamp_kind": "JAMP_CAPTURE_TIME",
                        "age_seconds": 0,
                        "age_basis": "deterministic E2E fixture",
                        "source_timestamp_utc": None,
                        "raw_sha256": "98fca5e0a61077522129f476961c31cef8d8f8f18803fb63d7d67576ab409301",
                    }
                ],
            }
        ],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
