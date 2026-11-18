"""HTTP contract tests for the tenant-scoped Arena API using deterministic provider fakes."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from jamp.api.app import create_app
from jamp.api.auth import OrganizationContext
from jamp.db import get_connection, init_schema, release_connection
from jamp.db.arena import (
    ArenaIdempotencyConflict,
    complete_arena_run,
    reserve_arena_run,
)


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
            "run_id": str(uuid.uuid4()),
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


def make_client(
    executor: FakeExecutor,
    organization_id: str = "org-a",
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> TestClient:
    from jamp.api import arena as arena_module

    async def authenticated_organization() -> OrganizationContext:
        return OrganizationContext(org_id=organization_id, org_name=organization_id)

    # Patch the dependency before create_app builds the Arena route; this makes
    # the route capture the deterministic tenant context used by this test.
    if monkeypatch is None:
        raise AssertionError("make_client requires pytest monkeypatch")
    monkeypatch.setattr(arena_module, "require_api_key", authenticated_organization)
    app = create_app(arena_executor=executor)
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
    with make_client(executor, monkeypatch=monkeypatch) as client:
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
    with make_client(executor, monkeypatch=monkeypatch) as client:
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
    with make_client(executor_a, "org-a", monkeypatch=monkeypatch) as client_a:
        response_a = client_a.post("/v1/arena/run", json=request_body("same-key"))
    with make_client(executor_b, "org-b", monkeypatch=monkeypatch) as client_b:
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

@pytest.fixture
def postgres_arena_organizations() -> Iterator[tuple[str, str]]:
    if not os.environ.get("JAMP_DATABASE_URL"):
        pytest.skip("Arena PostgreSQL integration tests require JAMP_DATABASE_URL")
    init_schema()
    organization_ids = (str(uuid.uuid4()), str(uuid.uuid4()))
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for organization_id in organization_ids:
                cursor.execute(
                    """
                    INSERT INTO organizations (id, name, api_key_hash)
                    VALUES (%s, %s, %s)
                    """,
                    (organization_id, "arena-integration", f"arena:{organization_id}"),
                )
        connection.commit()
        yield organization_ids
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            for organization_id in organization_ids:
                # Respect the existing RESTRICT foreign keys in the shared test schema.
                cursor.execute(
                    """
                    DELETE FROM evidence_chain
                    USING verdicts
                    WHERE evidence_chain.verdict_id = verdicts.id
                      AND verdicts.organization_id = %s
                    """,
                    (organization_id,),
                )
                cursor.execute(
                    "DELETE FROM verdicts WHERE organization_id = %s",
                    (organization_id,),
                )
                # arena_results are removed by arena_runs ON DELETE CASCADE.
                cursor.execute(
                    "DELETE FROM arena_runs WHERE organization_id = %s",
                    (organization_id,),
                )
                cursor.execute(
                    "DELETE FROM organizations WHERE id = %s",
                    (organization_id,),
                )
        connection.commit()
        release_connection(connection)


def test_postgres_arena_idempotency_and_tenant_isolation(
    postgres_arena_organizations: tuple[str, str],
):
    organization_a, organization_b = postgres_arena_organizations
    first, created = reserve_arena_run(
        organization_id=organization_a,
        idempotency_key="shared-client-key",
        prompt="same prompt",
        models=["model_a", "model_b"],
    )
    assert created is True
    persisted_results = [
        {
            "model": "model_a",
            "execution_status": "COMPLETED",
            "evidence_verdict": "UNKNOWN",
            "raw_response": "answer A",
            "trace_id": f"{first['run_id']}_model-a",
            "cost_estimate_rub": "UNKNOWN",
            "error": None,
        },
        {
            "model": "model_b",
            "execution_status": "FAILED",
            "evidence_verdict": "UNKNOWN",
            "raw_response": None,
            "trace_id": f"{first['run_id']}_model-b",
            "cost_estimate_rub": "UNKNOWN",
            "error": {"type": "TimeoutError"},
        },
    ]
    complete_arena_run(
        organization_id=organization_a,
        run_id=first["run_id"],
        status="PARTIAL",
        results=persisted_results,
    )

    replay, replayed = reserve_arena_run(
        organization_id=organization_a,
        idempotency_key="shared-client-key",
        prompt="same prompt",
        models=["model_a", "model_b"],
    )
    assert replayed is False
    assert replay == {
        "run_id": first["run_id"],
        "status": "PARTIAL",
        "results": persisted_results,
    }

    other_tenant, other_created = reserve_arena_run(
        organization_id=organization_b,
        idempotency_key="shared-client-key",
        prompt="same prompt",
        models=["model_a", "model_b"],
    )
    assert other_created is True
    assert other_tenant["run_id"] != first["run_id"]

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM arena_results AS results
                JOIN arena_runs AS runs ON runs.id = results.run_id
                WHERE runs.organization_id = %s
                """,
                (organization_a,),
            )
            result_count = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM arena_runs
                WHERE organization_id = %s AND idempotency_key = %s
                """,
                (organization_b, "shared-client-key"),
            )
            other_tenant_count = cursor.fetchone()[0]
        connection.commit()
    finally:
        release_connection(connection)
    assert result_count == 2
    assert other_tenant_count == 1


def test_postgres_arena_rejects_idempotency_key_payload_conflict(
    postgres_arena_organizations: tuple[str, str],
):
    organization_a, _ = postgres_arena_organizations
    reserve_arena_run(
        organization_id=organization_a,
        idempotency_key="conflicting-key",
        prompt="original",
        models=["model_a"],
    )
    with pytest.raises(ArenaIdempotencyConflict):
        reserve_arena_run(
            organization_id=organization_a,
            idempotency_key="conflicting-key",
            prompt="changed",
            models=["model_a"],
        )
