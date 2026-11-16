"""Browser dashboard authentication and evidence-only graph rendering tests."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from jamp.api import auth as auth_module

pytestmark = pytest.mark.real_auth

app_module = importlib.import_module("jamp.api.app")
VALID_API_KEY = "dashboard-web-test-key"
VERDICT_ID = "5fda8c13-6d6e-4c66-9a2d-36d9fb7c2a11"

GRAPH = {
    "nodes": [
        {
            "id": f"verdict:{VERDICT_ID}",
            "type": "verdict",
            "status": "HALLUCINATION_CAUGHT",
            "package": "missing-package",
            "created_at": "2026-11-06T10:00:00+00:00",
            "code_hash": "a" * 64,
        },
        {
            "id": "evidence:evidence-1",
            "type": "evidence",
            "sequence_no": 0,
            "evidence_type": "provenance",
            "payload": {"status": "NOT_FOUND", "reason": "package_not_found"},
            "payload_hash": "b" * 64,
            "created_at": "2026-11-06T10:00:00+00:00",
        },
    ],
    "edges": [
        {
            "id": f"evidence:evidence-1->belongs_to->verdict:{VERDICT_ID}",
            "source": "evidence:evidence-1",
            "target": f"verdict:{VERDICT_ID}",
            "relation": "belongs_to",
        }
    ],
}


@pytest.fixture
def dashboard_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "dashboard-web-test-secret")
    monkeypatch.setattr(
        auth_module,
        "_lookup_by_hash",
        lambda _digest: ("dashboard-org", "Dashboard Test", False),
    )
    monkeypatch.setattr(
        auth_module,
        "_lookup_by_id",
        lambda org_id: (org_id, "Dashboard Test", False),
    )
    monkeypatch.setattr(
        app_module,
        "list_verdicts_for_organization",
        lambda **_kwargs: {
            "items": [
                {
                    "verdict_id": VERDICT_ID,
                    "status": "HALLUCINATION_CAUGHT",
                    "package": "missing-package",
                    "created_at": "2026-11-06T10:00:00+00:00",
                    "code_hash": "a" * 64,
                }
            ],
            "limit": 1,
            "offset": 0,
            "total": 1,
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_verdict_graph_for_organization",
        lambda **_kwargs: GRAPH,
    )
    monkeypatch.setattr(
        app_module,
        "get_verdict_stats_for_organization",
        lambda **_kwargs: {
            "total_checks": 1,
            "hallucinations_caught": 1,
            "inconclusive": 0,
            "status_counts": {
                "CLEAN": 0,
                "SUSPICIOUS": 0,
                "HALLUCINATION_CAUGHT": 1,
                "INCONCLUSIVE": 0,
                "INTEGRITY_VIOLATED": 0,
            },
            "time_window": "all_time",
            "denominator": "persisted_verdict_rows",
        },
    )
    return TestClient(app_module.create_app(executor=lambda _model, _payload: {}))


def test_dashboard_requires_auth_and_exposes_login_page(
    dashboard_client: TestClient,
) -> None:
    protected = dashboard_client.get("/dashboard", follow_redirects=False)
    assert protected.status_code == 303
    assert protected.headers["location"] == "/dashboard/login"
    assert dashboard_client.get("/dashboard/login").status_code == 200
    assert dashboard_client.get("/v1/verdicts").status_code == 401


def test_login_issues_http_only_session_and_reads_tenant_data(
    dashboard_client: TestClient,
) -> None:
    login = dashboard_client.post(
        "/dashboard/login",
        data={"api_key": VALID_API_KEY},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert login.headers["location"] == "/"
    cookie_header = login.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=strict" in cookie_header
    assert "jamp_dashboard_session=" in cookie_header

    page = dashboard_client.get("/dashboard")
    assert page.status_code == 200
    assert "Dashboard Test" in page.text
    assert VALID_API_KEY not in page.text

    verdicts = dashboard_client.get("/v1/verdicts?limit=1")
    assert verdicts.status_code == 200
    assert verdicts.json()["items"][0]["verdict_id"] == VERDICT_ID

    graph = dashboard_client.get(f"/v1/verdicts/{VERDICT_ID}/graph")
    assert graph.status_code == 200
    assert graph.json() == GRAPH

    stats = dashboard_client.get("/v1/stats")
    assert stats.status_code == 200
    assert stats.json()["hallucinations_caught"] == 1

    write_attempt = dashboard_client.post("/v1/verify", json={})
    assert write_attempt.status_code == 403


def test_login_rejects_unknown_or_disabled_api_keys(
    dashboard_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_module, "_lookup_by_hash", lambda _digest: None)
    unknown = dashboard_client.post(
        "/dashboard/login",
        data={"api_key": "unknown-key"},
        follow_redirects=False,
    )
    assert unknown.status_code == 401

    monkeypatch.setattr(
        auth_module,
        "_lookup_by_hash",
        lambda _digest: ("dashboard-org", "Dashboard Test", True),
    )
    disabled = dashboard_client.post(
        "/dashboard/login",
        data={"api_key": VALID_API_KEY},
        follow_redirects=False,
    )
    assert disabled.status_code == 403


def test_dashboard_static_asset_contains_no_model_or_engine_fiction(
    dashboard_client: TestClient,
) -> None:
    response = dashboard_client.get("/dashboard-static/dashboard.js")
    assert response.status_code == 200
    assert 'getJson("/v1/verdicts?limit=1")' in response.text
    assert "DeepSeek V4" not in response.text
    assert "JAMP Engine" not in response.text
    assert "AST Check" not in response.text
    assert "PyPI Check" not in response.text


def test_ui_verify_bff_requires_authenticated_session_and_csrf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jamp.api.auth import (
        DASHBOARD_CSRF_COOKIE,
        DASHBOARD_SESSION_COOKIE,
        OrganizationContext,
    )
    from jamp.server.web import routes as web_routes

    monkeypatch.setenv("JAMP_UI_ALLOWED_ORIGINS", "http://localhost:5173")
    monkeypatch.delenv("JAMP_API_KEY", raising=False)
    monkeypatch.setattr(
        auth_module,
        "_lookup_by_hash",
        lambda _digest: ("ui-org", "UI Test", False),
    )
    monkeypatch.setattr(
        auth_module,
        "_lookup_by_id",
        lambda org_id: (org_id, "UI Test", False),
    )
    calls: list[tuple[dict, OrganizationContext]] = []
    organization = OrganizationContext(org_id="ui-org", org_name="UI Test")

    def fake_verify(payload: dict, resolved_org: OrganizationContext) -> dict:
        calls.append((payload, resolved_org))
        return {
            "status": "NO_CLAIMS",
            "system_warnings": ["No claims extracted."],
            "claims": [],
            "provider_errors": [],
            "trace_id": "vtext-test",
        }

    original_register = web_routes.register_ui_verify

    def register_with_mock(app, _verify_func) -> None:
        original_register(app, fake_verify)

    monkeypatch.setattr(web_routes, "register_ui_verify", register_with_mock)
    client = TestClient(app_module.create_app(executor=lambda _model, _payload: {}))

    unauthenticated = client.post(
        "/api/ui_verify",
        json={"text": "A test statement"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert unauthenticated.status_code == 401

    login = client.post(
        "/dashboard/login",
        data={"api_key": VALID_API_KEY},
        follow_redirects=False,
    )
    assert login.status_code == 303
    csrf_value = client.cookies.get(DASHBOARD_CSRF_COOKIE)
    assert client.cookies.get(DASHBOARD_SESSION_COOKIE)
    assert csrf_value
    set_cookies = login.headers.get_list("set-cookie")
    session_cookie = next(
        value for value in set_cookies if value.startswith(f"{DASHBOARD_SESSION_COOKIE}=")
    )
    csrf_cookie = next(
        value for value in set_cookies if value.startswith(f"{DASHBOARD_CSRF_COOKIE}=")
    )
    assert "httponly" in session_cookie.lower()
    assert "httponly" not in csrf_cookie.lower()
    assert "samesite=strict" in session_cookie.lower()
    assert "samesite=strict" in csrf_cookie.lower()

    missing_csrf = client.post(
        "/api/ui_verify",
        json={"text": "A test statement"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert missing_csrf.status_code == 403

    invalid_csrf = client.post(
        "/api/ui_verify",
        json={"text": "A test statement"},
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": "attacker-controlled"},
    )
    assert invalid_csrf.status_code == 403

    monkeypatch.setattr(
        web_routes,
        "authenticate_api_key",
        lambda _token: pytest.fail("BFF must not use a global API key"),
    )
    accepted = client.post(
        "/api/ui_verify",
        json={"text": "A test statement"},
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_value},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "NO_CLAIMS"
    assert calls == [({"text": "A test statement"}, organization)]
    assert VALID_API_KEY not in accepted.text


def test_ui_verify_bff_rejects_untrusted_origin_and_tampered_csrf(
    dashboard_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jamp.api.auth import DASHBOARD_CSRF_COOKIE

    monkeypatch.setenv("JAMP_UI_ALLOWED_ORIGINS", "http://localhost:5173")
    login = dashboard_client.post(
        "/dashboard/login",
        data={"api_key": VALID_API_KEY},
        follow_redirects=False,
    )
    assert login.status_code == 303
    csrf_value = dashboard_client.cookies.get(DASHBOARD_CSRF_COOKIE)
    assert csrf_value

    rejected_origin = dashboard_client.post(
        "/api/ui_verify",
        json={"text": "A test statement"},
        headers={"Origin": "https://attacker.example", "X-CSRF-Token": csrf_value},
    )
    assert rejected_origin.status_code == 403

    session_value = dashboard_client.cookies.get("jamp_dashboard_session", "")
    tampered_cookie = dashboard_client.post(
        "/api/ui_verify",
        json={"text": "A test statement"},
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf_value,
            "Cookie": (
                f"jamp_dashboard_session={session_value}; "
                f"{DASHBOARD_CSRF_COOKIE}=tampered"
            ),
        },
    )
    assert tampered_cookie.status_code == 403
