"""Deterministic browser fixture; it never represents live MOEX data."""

from __future__ import annotations

from urllib.parse import parse_qs

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="JAMP Playwright E2E fixture")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/dashboard/login", response_class=HTMLResponse)
def login_page() -> str:
    return """<!doctype html><html><body>
    <form method="post" action="/dashboard/login">
      <input name="api_key" type="password" required>
      <button type="submit">Войти</button>
    </form></body></html>"""


@app.post("/dashboard/login")
async def login(request: Request) -> RedirectResponse:
    form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    if form.get("api_key", [""])[0] != "e2e-test-key":
        raise HTTPException(status_code=401, detail="invalid test key")
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("jamp_dashboard_session", "e2e-session", httponly=True, samesite="strict", path="/")
    response.set_cookie("jamp_dashboard_csrf", "e2e-csrf", httponly=False, samesite="strict", path="/")
    return response


@app.post("/ui_verify")
def ui_verify(request: Request, _payload: dict[str, object]) -> dict[str, object]:
    if request.cookies.get("jamp_dashboard_session") != "e2e-session":
        raise HTTPException(status_code=401, detail="missing test session")
    if request.cookies.get("jamp_dashboard_csrf") != "e2e-csrf" or request.headers.get("x-csrf-token") != "e2e-csrf":
        raise HTTPException(status_code=403, detail="invalid test CSRF token")
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
                        "raw_body_base64": (
                            "eyJmaXh0dXJlIjoiSkFNUCBQbGF5d3JpZ2h0IEUyRSIs"
                            "InNvdXJjZSI6Ik1PRVggSVNTIiwiYWN0dWFsX3ZhbHVlIjoyOTkuMjZ9"
                        ),
                        "actual_value": 299.26,
                        "timestamp_utc": "2026-11-16T00:00:00Z",
                        "timestamp_kind": "JAMP_CAPTURE_TIME",
                        "age_seconds": 0,
                        "age_basis": "deterministic E2E fixture",
                        "source_timestamp_utc": None,
                        "raw_sha256": (
                            "98fca5e0a61077522129f476961c31cef8d8f8f18803fb63d7d67576ab409301"
                        ),
                    }
                ],
            }
        ],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
