"""Browser dashboard GitHub OAuth and evidence-only graph tests."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from jamp.api import auth as auth_module
from jamp.server.web import routes as routes_module

pytestmark = pytest.mark.real_auth

app_module = importlib.import_module("jamp.api.app")
ALLOWED_GITHUB_USER_ID = 123456
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
def dashboard_client(
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "dashboard-web-test-secret")
    monkeypatch.setenv("JAMP_GITHUB_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("JAMP_GITHUB_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv(
        "JAMP_GITHUB_OAUTH_REDIRECT_URI",
        "https://example.test/dashboard/oauth/callback",
    )
    monkeypatch.setenv("JAMP_GITHUB_ALLOWED_USER_ID", str(ALLOWED_GITHUB_USER_ID))
    monkeypatch.setenv("JAMP_GITHUB_OAUTH_ORG_ID", "dashboard-org")
    monkeypatch.delenv("JAMP_COOKIE_SECURE", raising=False)
    monkeypatch.setattr(
        auth_module,
        "_lookup_by_id",
        lambda _org_id: ("dashboard-org", "Dashboard Test", False),
    )
    monkeypatch.setattr(
        routes_module,
        "_exchange_github_code",
        lambda _code, _config: "test-access-token",
    )
    monkeypatch.setattr(
        routes_module,
        "_fetch_github_user",
        lambda _token: {"id": ALLOWED_GITHUB_USER_ID},
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


def test_dashboard_requires_auth_and_exposes_github_login_page(
    dashboard_client: TestClient,
) -> None:
    protected = dashboard_client.get("/dashboard", follow_redirects=False)
    assert protected.status_code == 303
    assert protected.headers["location"] == "/dashboard/login"

    login_page = dashboard_client.get("/dashboard/login")
    assert login_page.status_code == 200
    assert "Войти через GitHub" in login_page.text
    assert 'name="api_key"' not in login_page.text
    assert dashboard_client.get("/v1/verdicts").status_code == 401


def test_github_oauth_creates_tenant_session_and_reads_dashboard_data(
    dashboard_client: TestClient,
) -> None:
    start = dashboard_client.get("/dashboard/oauth/start", follow_redirects=False)
    assert start.status_code == 303
    assert start.headers["location"].startswith(
        "https://github.com/login/oauth/authorize?"
    )
    state_cookie = start.headers["set-cookie"].lower()
    assert "jamp_github_oauth_state=" in state_cookie
    assert "httponly" in state_cookie
    assert "samesite=lax" in state_cookie

    state = dashboard_client.cookies.get("jamp_github_oauth_state")
    assert state
    callback = dashboard_client.get(
        "/dashboard/oauth/callback",
        params={"code": "github-one-time-code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"] == "/dashboard"
    session_cookie = callback.headers["set-cookie"].lower()
    assert "jamp_dashboard_session=" in session_cookie
    assert "httponly" in session_cookie
    assert "samesite=strict" in session_cookie

    page = dashboard_client.get("/dashboard")
    assert page.status_code == 200
    assert "Dashboard Test" in page.text

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


def test_github_oauth_rejects_invalid_state_and_unapproved_identity(
    dashboard_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_state = dashboard_client.get(
        "/dashboard/oauth/callback",
        params={"code": "github-one-time-code", "state": "attacker-state"},
    )
    assert invalid_state.status_code == 400

    dashboard_client.get("/dashboard/oauth/start", follow_redirects=False)
    state = dashboard_client.cookies.get("jamp_github_oauth_state")
    assert state
    monkeypatch.setattr(
        routes_module,
        "_fetch_github_user",
        lambda _token: {"id": ALLOWED_GITHUB_USER_ID + 1},
    )
    denied = dashboard_client.get(
        "/dashboard/oauth/callback",
        params={"code": "github-one-time-code", "state": state},
    )
    assert denied.status_code == 403


def test_github_oauth_rejects_disabled_organization(
    dashboard_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = dashboard_client.get("/dashboard/oauth/start", follow_redirects=False)
    state = dashboard_client.cookies.get("jamp_github_oauth_state")
    assert state
    monkeypatch.setattr(
        auth_module,
        "_lookup_by_id",
        lambda _org_id: ("dashboard-org", "Dashboard Test", True),
    )
    denied = dashboard_client.get(
        "/dashboard/oauth/callback",
        params={"code": "github-one-time-code", "state": state},
    )
    assert denied.status_code == 403


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
