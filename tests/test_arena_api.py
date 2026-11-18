"""HTTP contract tests for the tenant-scoped Arena API using deterministic provider fakes."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from jamp.api.app import create_app
from jamp.api.auth import OrganizationContext, require_api_key


class FakeExecutor:
    def __init__(self, failing_models: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.failing_models = failing_models or set()

    def execute(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> dict[str, Any]:
        self.calls.append(model)
        if model in self.failing_models:
            raise RuntimeError("provider unavailable")
        return {
            "raw_body": '{"choices":[{"message":{"content":"answer"}}]}',
            "raw_body_sha256": "a" * 64,
            "model_id": model,
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "content": f"answer from {model}",
            "cost_estimate_rub": "UNKNOWN",
            "error": None,
        }


@pytest.fixture
def arena_store(monkeypatch):
    from jamp.api import arena as arena_module
    from jamp.db.arena import ArenaIdempotencyConflict

    records: dict[tuple[str, str], dict[str, Any]] = {}

    def reserve(*, organization_id, idempotency_key, prompt, models):
        key = (organization_id, idempotency_key)
        if key in records:
            current = records[key]
            if current["prompt"] != prompt or current["models"] != models:
                raise ArenaIdempotencyConflict
            return {
                "run_id": current["run_id"],
                "status": current["status"],
                "results": current["results"],
            }, False
        record = {
            "run_id": f"run-{len(records) + 1}",
            "prompt": prompt,
            "models": list(models),
            "status": "RUNNING",
            "results": [],
        }
        records[key] = record
        return {"run_id": record["run_id"], "status": "RUNNING", "results": []}, True

    def complete(*, organization_id, run_id, status, results):
        record = next(
            item for (org, _), item in records.items()
            if org == organization_id and item["run_id"] == run_id
        )
        record["status"] = status
        record["results"] = results

    monkeypatch.setattr(arena_module, "reserve_arena_run", reserve)
    monkeypatch.setattr(arena_module, "complete_arena_run", complete)
    return records


def make_client(executor: FakeExecutor, organization_id: str = "org-a") -> TestClient:
    app = create_app(arena_executor=executor)
    app.dependency_overrides[require_api_key] = lambda: OrganizationContext(
        org_id=organization_id,
        org_name=organization_id,
    )
    return TestClient(app)


def request_body(key: str = "client-uuid-123") -> dict[str, Any]:
    return {
        "prompt": "Analyze product X launch risks",
        "models": ["model_a", "model_b"],
        "idempotency_key": key,
    }


def test_arena_returns_separate_execution_and_evidence_statuses(monkeypatch, arena_store):
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "arena-test-secret")
    executor = FakeExecutor()
    with make_client(executor) as client:
        response = client.post("/v1/arena/run", json=request_body())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert [item["execution_status"] for item in body["results"]] == ["COMPLETED", "COMPLETED"]
    assert [item["evidence_verdict"] for item in body["results"]] == ["UNKNOWN", "UNKNOWN"]
    assert body["results"][0]["raw_response"] == "answer from model_a"
    assert body["results"][0]["cost_estimate_rub"] == "UNKNOWN"
    assert len(executor.calls) == 2
    assert arena_store[("org-a", "client-uuid-123")]["results"] == body["results"]


def test_arena_idempotency_replays_cached_result_without_provider_calls(monkeypatch, arena_store):
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "arena-test-secret")
    executor = FakeExecutor()
    with make_client(executor) as client:
        first = client.post("/v1/arena/run", json=request_body())
        second = client.post("/v1/arena/run", json=request_body())

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(executor.calls) == 2


def test_arena_idempotency_rejects_key_reuse_with_different_payload(monkeypatch, arena_store):
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "arena-test-secret")
    executor = FakeExecutor()
    with make_client(executor) as client:
        first = client.post("/v1/arena/run", json=request_body())
        changed = request_body()
        changed["prompt"] = "A different prompt"
        second = client.post("/v1/arena/run", json=changed)

    assert first.status_code == 200
    assert second.status_code == 409
    assert len(executor.calls) == 2


def test_arena_tenant_isolation_uses_authenticated_organization(monkeypatch, arena_store):
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "arena-test-secret")
    executor_a = FakeExecutor()
    executor_b = FakeExecutor()
    with make_client(executor_a, "org-a") as client_a:
        response_a = client_a.post("/v1/arena/run", json=request_body("same-key"))
    with make_client(executor_b, "org-b") as client_b:
        response_b = client_b.post("/v1/arena/run", json=request_body("same-key"))

    assert response_a.status_code == response_b.status_code == 200
    assert response_a.json()["run_id"] != response_b.json()["run_id"]
    assert ("org-a", "same-key") in arena_store
    assert ("org-b", "same-key") in arena_store
    assert len(executor_a.calls) == len(executor_b.calls) == 2


def test_arena_partial_failure_is_visible_per_model(monkeypatch, arena_store):
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "arena-test-secret")
    executor = FakeExecutor(failing_models={"model_b"})
    with make_client(executor) as client:
        response = client.post("/v1/arena/run", json=request_body())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PARTIAL"
    assert body["results"][0]["execution_status"] == "COMPLETED"
    assert body["results"][1]["execution_status"] == "FAILED"
    assert body["results"][1]["raw_response"] is None
    assert body["results"][1]["evidence_verdict"] == "UNKNOWN"


def test_arena_rejects_tenant_supplied_in_request_body(monkeypatch, arena_store):
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "arena-test-secret")
    executor = FakeExecutor()
    payload = {**request_body(), "organization_id": "org-victim"}
    with make_client(executor) as client:
        response = client.post("/v1/arena/run", json=payload)

    assert response.status_code == 422
    assert executor.calls == []
    assert arena_store == {}
