"""DEC-001 tenant isolation baseline using the real API, PostgreSQL auth and JSONL store.

The 18 declared controls are never silently removed. Conditional record creation
uses explicit pytest skips; unavailable PostgreSQL skips the complete module.
No authentication, persistence, or read-path dependency is mocked or patched.
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx2 import ASGITransport, AsyncClient

from jamp.api import auth
from jamp.api.app import _verdict_signing_key, create_app
from jamp.db import get_connection, init_schema, release_connection
from jamp.runtime.persistence import AuditPersistence
from jamp.runtime.verdict import JampVerdict


pytestmark = [
    pytest.mark.real_auth,
    pytest.mark.skipif(
        not os.environ.get("JAMP_DATABASE_URL"),
        reason="PostgreSQL integration tests require JAMP_DATABASE_URL",
    ),
]


CONTROL_CASES = [
    pytest.param("trace", "positive", "A", "A", id="trace-positive-org-a"),
    pytest.param("trace", "positive", "B", "B", id="trace-positive-org-b"),
    pytest.param("trace", "cross_org", "A", "B", id="trace-cross-org-b-to-a"),
    pytest.param("trace", "cross_org", "B", "A", id="trace-cross-org-a-to-b"),
    pytest.param("trace", "missing", "A", None, id="trace-missing-org-a"),
    pytest.param("trace", "missing", "B", None, id="trace-missing-org-b"),
    pytest.param(
        "universal_verdict", "positive", "A", "A", id="universal-positive-org-a"
    ),
    pytest.param(
        "universal_verdict", "positive", "B", "B", id="universal-positive-org-b"
    ),
    pytest.param(
        "universal_verdict", "cross_org", "A", "B", id="universal-cross-org-b-to-a"
    ),
    pytest.param(
        "universal_verdict", "cross_org", "B", "A", id="universal-cross-org-a-to-b"
    ),
    pytest.param(
        "universal_verdict", "missing", "A", None, id="universal-missing-org-a"
    ),
    pytest.param(
        "universal_verdict", "missing", "B", None, id="universal-missing-org-b"
    ),
    pytest.param("verdict", "positive", "A", "A", id="verdict-positive-org-a"),
    pytest.param("verdict", "positive", "B", "B", id="verdict-positive-org-b"),
    pytest.param("verdict", "cross_org", "A", "B", id="verdict-cross-org-b-to-a"),
    pytest.param("verdict", "cross_org", "B", "A", id="verdict-cross-org-a-to-b"),
    pytest.param("verdict", "missing", "A", None, id="verdict-missing-org-a"),
    pytest.param("verdict", "missing", "B", None, id="verdict-missing-org-b"),
]


READ_ROUTES = {
    "trace": "/v1/provenance/{trace_id}",
    "verdict": "/v1/jamp-verdict/{trace_id}",
    "universal_verdict": "/v1/universal-verdict/{trace_id}",
}


@pytest.fixture(scope="module", autouse=True)
def _postgres_schema() -> None:
    """Initialize the actual PostgreSQL schema used by API-key authentication."""
    init_schema()


@pytest.fixture(autouse=True)
def _real_auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure the HMAC secret; authentication and database lookup stay real."""
    monkeypatch.setenv(auth._ENV_SECRET, "dec001-integration-test-hmac-secret")


@pytest.fixture
def two_orgs() -> dict[str, dict[str, str]]:
    """Create two real organizations with independently hashed bearer keys."""
    created_ids: list[str] = []
    organizations: dict[str, dict[str, str]] = {}

    for label in ("A", "B"):
        token = f"dec001-{label.lower()}-{uuid.uuid4().hex}"
        key_hash = auth.hash_api_key(token)
        org_id = str(uuid.uuid4())
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO organizations "
                    "(id, name, api_key_hash, disabled, plan) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (org_id, f"dec001-org-{label}", key_hash, False, "free"),
                )
            connection.commit()
        finally:
            release_connection(connection)

        created_ids.append(org_id)
        organizations[label] = {
            "org_id": org_id,
            "token": token,
        }

    try:
        yield organizations
    finally:
        if created_ids:
            connection = get_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM organizations WHERE id = ANY(%s)",
                        (created_ids,),
                    )
                connection.commit()
            finally:
                release_connection(connection)


@pytest.fixture
def audit_path(tmp_path: Any, monkeypatch: pytest.MonkeyPatch):
    """Point the real app at one shared JSONL directory for both organizations."""
    path = tmp_path / "shared-audit" / "provenance_traces.jsonl"
    monkeypatch.setenv("JAMP_AUDIT_PATH", str(path))
    return path


@pytest.fixture
def audit_store(audit_path) -> AuditPersistence:
    """Read records through the production persistence implementation."""
    store = AuditPersistence(audit_path)
    assert store.storage_path.parent == store.verdicts_path.parent
    assert store.storage_path.parent == store.universal_verdicts_path.parent
    return store


@pytest_asyncio.fixture
async def client(audit_path) -> AsyncIterator[AsyncClient]:
    """Run create_app through an actual ASGI transport and its startup hooks."""
    app = create_app()
    # ASGITransport deliberately does not manage lifespan. Enter the router's
    # ASGI lifespan context explicitly; APIRouter has no startup()/shutdown()
    # methods, and the context also guarantees shutdown when the test exits.
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://jamp.test",
        ) as test_client:
            yield test_client


def _headers(organization: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {organization['token']}"}


async def _create_trace_via_api(
    client: AsyncClient,
    organization: dict[str, str],
    audit_store: AuditPersistence,
) -> tuple[str, str]:
    """Create a real refusal trace through authenticated POST /v1/execute."""
    request_marker = f"dec001-trace-{uuid.uuid4().hex}"
    response = await client.post(
        "/v1/execute",
        headers=_headers(organization),
        json={"request_id": request_marker},
    )
    assert response.status_code == 422, (
        "The intentionally unclassifiable request must take the real fail-closed "
        f"trace-creation path; got HTTP {response.status_code}: {response.text}"
    )

    body = response.json()
    trace_id = body.get("trace_id")
    assert isinstance(trace_id, str) and trace_id
    stored = audit_store.read_trace_by_id(trace_id, organization_id=organization["org_id"])
    assert stored is not None, "POST /v1/execute returned a trace that JSONL did not persist"
    assert stored.get("request_id") == request_marker
    return trace_id, request_marker


async def _create_universal_verdict_via_api(
    client: AsyncClient,
    organization: dict[str, str],
    audit_store: AuditPersistence,
) -> tuple[str, str]:
    """Create a genuinely signed, explicitly INCONCLUSIVE UniversalVerdict."""
    signing_key = _verdict_signing_key()
    if signing_key is None:
        pytest.skip("signing unavailable: production signing key is not configured")

    trace_id = f"dec001-uv-{uuid.uuid4().hex}"
    marker = f"dec001-spec-{uuid.uuid4().hex}"
    verdict = JampVerdict(
        trace_id=trace_id,
        status="INCONCLUSIVE",
        provider_model_id=None,
        evidence_hash="sha256:" + hashlib.sha256(marker.encode("utf-8")).hexdigest(),
        timestamp=time.time(),
        execution_status="INCONCLUSIVE",
        model_verification="INCONCLUSIVE",
        claims=[],
        aggregate_status="INCONCLUSIVE",
        critical_unverified=[],
    ).sign(signing_key)

    response = await client.post(
        "/v1/universal-verdict",
        headers=_headers(organization),
        json={
            "spec_id": marker,
            "criteria_id": f"dec001-criteria-{uuid.uuid4().hex}",
            "jamp_verdict": verdict.to_dict(),
            "evidence_refs": [],
        },
    )
    if response.status_code == 503:
        pytest.skip("signing unavailable: POST /v1/universal-verdict returned 503")
    assert response.status_code == 200, (
        "The real UniversalVerdict create route rejected a correctly signed "
        f"INCONCLUSIVE JampVerdict: HTTP {response.status_code}: {response.text}"
    )

    stored = audit_store.read_universal_verdict_by_id(
        trace_id, organization_id=organization["org_id"]
    )
    assert stored is not None, (
        "POST /v1/universal-verdict succeeded but the production JSONL record is absent"
    )
    assert stored["universal_verdict"]["spec_ref"]["spec_id"] == marker
    return trace_id, marker


async def _create_verdict_via_execute(
    client: AsyncClient,
    organization: dict[str, str],
    audit_store: AuditPersistence,
) -> tuple[str, str]:
    """Attempt the real execution path; never manufacture a VERIFIED verdict."""
    request_marker = f"dec001-verdict-{uuid.uuid4().hex}"
    response = await client.post(
        "/v1/execute",
        headers=_headers(organization),
        json={
            "intent": "search_and_extraction",
            "prompt": (
                "Extract the explicitly stated company name from this text: "
                "Example Company announced a product update."
            ),
            "request_id": request_marker,
        },
    )
    body = response.json()
    trace_id = body.get("trace_id")
    assert isinstance(trace_id, str) and trace_id, (
        "The real execution route did not return a trace_id: "
        f"HTTP {response.status_code}: {response.text}"
    )

    trace = audit_store.read_trace_by_id(trace_id, organization_id=organization["org_id"])
    assert trace is not None, "The execution route did not persist its trace"

    stored_verdict = audit_store.read_verdict_by_id(
        trace_id, organization_id=organization["org_id"]
    )
    if stored_verdict is not None:
        return trace_id, stored_verdict["evidence_hash"]

    evidence_status = body.get("evidence_status")
    reason = body.get("reason")
    if body.get("status") in {"REFUSE", "INCONCLUSIVE"}:
        pytest.skip(
            "VERIFIED branch not triggered: execution refused/inconclusive "
            f"(reason={reason or 'not reported'}, HTTP {response.status_code})"
        )
    if response.status_code == 503 and reason in {
        "PROVIDER_NOT_CONFIGURED",
        "SIGNING_KEY_NOT_CONFIGURED",
    }:
        pytest.skip(
            "VERIFIED branch not triggered: "
            f"{reason} (HTTP {response.status_code})"
        )
    if response.status_code == 200 and evidence_status != "VERIFIED":
        pytest.skip(
            "VERIFIED branch not triggered: "
            f"evidence_status={evidence_status!r}"
        )

    pytest.fail(
        "Execution reported a VERIFIED-capable result but no Verdict was persisted, "
        f"or failed unexpectedly: HTTP {response.status_code}, "
        f"evidence_status={evidence_status!r}, reason={reason!r}"
    )


async def _create_record(
    resource: str,
    client: AsyncClient,
    organization: dict[str, str],
    audit_store: AuditPersistence,
) -> tuple[str, str]:
    if resource == "trace":
        return await _create_trace_via_api(client, organization, audit_store)
    if resource == "universal_verdict":
        return await _create_universal_verdict_via_api(
            client, organization, audit_store
        )
    if resource == "verdict":
        return await _create_verdict_via_execute(client, organization, audit_store)
    raise AssertionError(f"Unknown DEC-001 resource type: {resource}")


def _assert_non_disclosing(
    response_text: str,
    *,
    trace_id: str,
    marker: str,
    owner_org_id: str,
) -> None:
    body = response_text.casefold()
    for protected_value in (trace_id, marker, owner_org_id):
        if protected_value:
            assert protected_value.casefold() not in body, (
                "Cross-organization response disclosed protected record data: "
                f"{protected_value!r}"
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource,control,caller_label,owner_label",
    CONTROL_CASES,
)
async def test_dec001_tenant_isolation_control(
    resource: str,
    control: str,
    caller_label: str,
    owner_label: str | None,
    client: AsyncClient,
    two_orgs: dict[str, dict[str, str]],
    audit_store: AuditPersistence,
) -> None:
    """Execute one of the 18 positive, cross-org, or missing-record controls."""
    route = READ_ROUTES[resource]
    caller = two_orgs[caller_label]

    if control == "missing":
        missing_trace_id = f"dec001-missing-{uuid.uuid4().hex}"
        response = await client.get(
            route.format(trace_id=missing_trace_id),
            headers=_headers(caller),
        )
        assert response.status_code == 404, (
            f"{resource} missing-record contract expected 404; "
            f"got HTTP {response.status_code}: {response.text}"
        )
        assert missing_trace_id not in response.text
        return

    assert owner_label in two_orgs
    owner = two_orgs[owner_label]
    trace_id, marker = await _create_record(
        resource,
        client,
        owner,
        audit_store,
    )
    response = await client.get(
        route.format(trace_id=trace_id),
        headers=_headers(caller),
    )

    if control == "positive":
        assert response.status_code == 200, (
            f"{resource} owner could not read its own record: "
            f"HTTP {response.status_code}: {response.text}"
        )
        body = response.json()
        assert body.get("trace_id") == trace_id
        assert marker in response.text
        return

    assert control == "cross_org"
    assert caller_label != owner_label
    assert response.status_code in {403, 404}, (
        f"{resource} cross-organization read was not refused: "
        f"HTTP {response.status_code}: {response.text}"
    )
    _assert_non_disclosing(
        response.text,
        trace_id=trace_id,
        marker=marker,
        owner_org_id=owner["org_id"],
    )
