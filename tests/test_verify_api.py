"""Contract tests for the authenticated code-verification endpoint."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from jamp.api import app as app_module
from jamp.api.app import create_app
from jamp.api.auth import OrganizationContext, require_api_key


def test_verify_endpoint_persists_and_replays_idempotently(monkeypatch):
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "test-secret")
    app = create_app()
    app.dependency_overrides[require_api_key] = lambda: OrganizationContext(
        org_id="org-c3-test", org_name="C3 Test"
    )
    result = {
        "status": "CLEAN",
        "package": "sample-package",
        "sample_id": "sample-1",
        "provenance": {"status": "TRUSTED"},
        "signature": {"status": "EXISTS"},
    }
    monkeypatch.setattr(
        "jamp.server.checks.engine.verify_code", lambda *args, **kwargs: result
    )
    saved = {
        "verdict_id": "00000000-0000-0000-0000-000000000001",
        "status": "CLEAN",
        "result": result,
        "evidence": [],
        "created_at": datetime.now(UTC).isoformat(),
        "code_hash": "a" * 64,
    }
    calls = []

    def persist(**kwargs):
        calls.append(kwargs)
        return saved, len(calls) == 1

    monkeypatch.setattr(app_module, "persist_or_get_verdict", persist)
    with TestClient(app) as client:
        headers = {"Idempotency-Key": "request-1"}
        body = {"code_str": "import sample", "package_name": "sample-package"}
        first = client.post("/v1/verify", json=body, headers=headers)
        replay = client.post("/v1/verify", json=body, headers=headers)
        conflict = client.post(
            "/v1/verify",
            json={**body, "code_str": "import other"},
            headers=headers,
        )
        missing_key = client.post("/v1/verify", json=body)
    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["verdict_id"] == replay.json()["verdict_id"]
    assert conflict.status_code == 201
    assert missing_key.status_code == 400
    assert len(calls) == 3
