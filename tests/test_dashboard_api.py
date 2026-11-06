from __future__ import annotations

import importlib
from uuid import uuid4

import pytest

pytestmark = pytest.mark.real_auth
from fastapi.testclient import TestClient

from jamp.api import auth as auth_module

app_module = importlib.import_module("jamp.api.app")
AUTH = {"Authorization": "Bearer dashboard-test-token"}


@pytest.fixture
def dashboard_client(monkeypatch):
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "dashboard-test-secret")
    monkeypatch.setattr(
        auth_module,
        "_lookup_by_hash",
        lambda _digest: ("dashboard-org", "Dashboard Test", False),
    )
    return TestClient(app_module.create_app(executor=lambda _model, _payload: {}))


def test_verdict_list_returns_tenant_scoped_cards(dashboard_client, monkeypatch):
    calls = []

    def list_verdicts(**kwargs):
        calls.append(kwargs)
        return {
            "items": [
                {
                    "verdict_id": str(uuid4()),
                    "status": "CLEAN",
                    "package": "sample-package",
                    "created_at": "2026-11-06T10:00:00+00:00",
                    "code_hash": "a" * 64,
                }
            ],
            "limit": 20,
            "offset": 0,
            "total": 1,
        }

    monkeypatch.setattr(app_module, "list_verdicts_for_organization", list_verdicts)
    response = dashboard_client.get("/v1/verdicts", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["package"] == "sample-package"
    assert calls == [
        {
            "organization_id": "dashboard-org",
            "limit": 20,
            "offset": 0,
            "status": None,
        }
    ]


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"limit": 0}, "limit must be between 1 and 100"),
        ({"limit": 101}, "limit must be between 1 and 100"),
        ({"offset": -1}, "offset must be non-negative"),
        ({"status": "QUALIFIED"}, "unsupported verdict status"),
    ],
)
def test_verdict_list_rejects_invalid_filters(dashboard_client, params, detail):
    response = dashboard_client.get("/v1/verdicts", params=params, headers=AUTH)
    assert response.status_code == 422
    assert response.json()["detail"] == detail


def test_verdict_list_requires_authentication(dashboard_client):
    response = dashboard_client.get("/v1/verdicts")
    assert response.status_code == 401


def test_verdict_graph_returns_only_persisted_projection(dashboard_client, monkeypatch):
    verdict_id = str(uuid4())
    calls = []
    graph = {
        "nodes": [
            {"id": f"verdict:{verdict_id}", "type": "verdict", "status": "CLEAN"},
            {
                "id": "evidence:evidence-1",
                "type": "evidence",
                "sequence_no": 0,
                "evidence_type": "provenance",
                "payload": {"status": "TRUSTED"},
                "payload_hash": "b" * 64,
            },
        ],
        "edges": [
            {
                "id": f"evidence:evidence-1->belongs_to->verdict:{verdict_id}",
                "source": "evidence:evidence-1",
                "target": f"verdict:{verdict_id}",
                "relation": "belongs_to",
            }
        ],
    }

    def get_graph(**kwargs):
        calls.append(kwargs)
        return graph

    monkeypatch.setattr(app_module, "get_verdict_graph_for_organization", get_graph)
    response = dashboard_client.get(
        f"/v1/verdicts/{verdict_id}/graph", headers=AUTH
    )

    assert response.status_code == 200
    assert response.json() == graph
    assert calls == [
        {"verdict_id": verdict_id, "organization_id": "dashboard-org"}
    ]


def test_verdict_graph_hides_missing_or_foreign_tenant(dashboard_client, monkeypatch):
    monkeypatch.setattr(
        app_module, "get_verdict_graph_for_organization", lambda **_kwargs: None
    )
    response = dashboard_client.get(
        f"/v1/verdicts/{uuid4()}/graph", headers=AUTH
    )
    assert response.status_code == 404


def test_stats_returns_real_tenant_aggregate(dashboard_client, monkeypatch):
    calls = []

    def get_stats(**kwargs):
        calls.append(kwargs)
        return {
            "total_checks": 3,
            "hallucinations_caught": 1,
            "inconclusive": 1,
            "status_counts": {
                "CLEAN": 1,
                "SUSPICIOUS": 0,
                "HALLUCINATION_CAUGHT": 1,
                "INCONCLUSIVE": 1,
                "INTEGRITY_VIOLATED": 0,
            },
            "time_window": "all_time",
            "denominator": "persisted_verdict_rows",
        }

    monkeypatch.setattr(app_module, "get_verdict_stats_for_organization", get_stats)
    response = dashboard_client.get("/v1/stats", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["total_checks"] == 3
    assert response.json()["hallucinations_caught"] == 1
    assert response.json()["inconclusive"] == 1
    assert calls == [{"organization_id": "dashboard-org"}]


def test_stats_empty_dataset_is_zero_not_missing(dashboard_client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_verdict_stats_for_organization",
        lambda **_kwargs: {
            "total_checks": 0,
            "hallucinations_caught": 0,
            "inconclusive": 0,
            "status_counts": {
                "CLEAN": 0,
                "SUSPICIOUS": 0,
                "HALLUCINATION_CAUGHT": 0,
                "INCONCLUSIVE": 0,
                "INTEGRITY_VIOLATED": 0,
            },
            "time_window": "all_time",
            "denominator": "persisted_verdict_rows",
        },
    )
    response = dashboard_client.get("/v1/stats", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["total_checks"] == 0
    assert all(value == 0 for value in response.json()["status_counts"].values())
