import io
import json
import zipfile

import pytest

from scripts.agents import daily_evidence_agent as agent
from scripts.agents.daily_evidence_agent import EvidenceError, event_delta


def test_initial_baseline_does_not_claim_new_events() -> None:
    current = {"pull_requests": [{"number": 1}], "workflow_runs": [{"id": 10}]}

    result = event_delta(current, None)

    assert result == {
        "mode": "INITIAL_BASELINE",
        "new_or_updated_prs": [],
        "new_or_updated_runs": [],
    }


def test_event_delta_detects_new_and_updated_items() -> None:
    previous = {
        "pull_requests": {"1": "2026-10-13T10:00:00Z"},
        "workflow_runs": {"10:1": "2026-10-13T10:00:00Z"},
    }
    current = {
        "pull_requests": [
            {"number": 1, "updated_at": "2026-10-14T10:00:00Z"},
            {"number": 2, "updated_at": "2026-10-14T11:00:00Z"},
        ],
        "workflow_runs": [
            {"id": 10, "run_attempt": 1, "updated_at": "2026-10-14T10:00:00Z"},
            {"id": 11, "run_attempt": 1, "updated_at": "2026-10-14T11:00:00Z"},
        ],
    }

    result = event_delta(current, previous)

    assert [item["number"] for item in result["new_or_updated_prs"]] == [1, 2]
    assert [item["id"] for item in result["new_or_updated_runs"]] == [10, 11]


def test_event_delta_ignores_unchanged_items() -> None:
    previous = {
        "pull_requests": {"1": "2026-10-14T10:00:00Z"},
        "workflow_runs": {"10:1": "2026-10-14T10:00:00Z"},
    }
    current = {
        "pull_requests": [{"number": 1, "updated_at": "2026-10-14T10:00:00Z"}],
        "workflow_runs": [{"id": 10, "run_attempt": 1, "updated_at": "2026-10-14T10:00:00Z"}],
    }

    result = event_delta(current, previous)

    assert result["new_or_updated_prs"] == []
    assert result["new_or_updated_runs"] == []


def valid_state() -> dict:
    return {
        "schema_version": "1.0",
        "saved_at": "2026-10-14T10:00:00Z",
        "pull_requests": {"12": "2026-10-14T10:00:00Z"},
        "workflow_runs": {"123:1": "2026-10-14T10:00:00Z"},
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda state: state.pop("saved_at"),
        lambda state: state.update(pull_requests=[]),
        lambda state: state.update(workflow_runs="not-an-object"),
        lambda state: state.update(pull_requests={"not-a-number": "2026-10-14T10:00:00Z"}),
        lambda state: state.update(workflow_runs={"123": "2026-10-14T10:00:00Z"}),
        lambda state: state.update(pull_requests={"12": None}),
    ],
)
def test_validate_state_rejects_missing_fields_and_invalid_types(mutate) -> None:
    state = valid_state()
    mutate(state)

    with pytest.raises(EvidenceError):
        agent.validate_state(state)


def test_validate_state_rejects_unsupported_schema() -> None:
    state = valid_state()
    state["schema_version"] = "99.0"

    with pytest.raises(EvidenceError, match="unsupported"):
        agent.validate_state(state)


def test_prior_state_rejects_malformed_github_artifact_response(monkeypatch) -> None:
    monkeypatch.setattr(agent, "github_request", lambda *args, **kwargs: {"artifacts": "bad"})

    with pytest.raises(EvidenceError, match="malformed"):
        agent.prior_state("owner/repo", "token", "99")


def test_prior_state_rejects_artifact_missing_archive_url(monkeypatch) -> None:
    monkeypatch.setattr(
        agent,
        "github_request",
        lambda *args, **kwargs: {
            "artifacts": [
                {
                    "name": agent.STATE_ARTIFACT,
                    "expired": False,
                    "created_at": "2026-10-14T10:00:00Z",
                    "workflow_run": {"id": 123, "head_repository_id": 1},
                }
            ]
        },
    )

    with pytest.raises(EvidenceError, match="archive URL"):
        agent.prior_state("owner/repo", "token", "99")


def test_prior_state_rejects_missing_artifact_provenance(monkeypatch) -> None:
    monkeypatch.setattr(
        agent,
        "github_request",
        lambda *args, **kwargs: {
            "artifacts": [
                {
                    "name": agent.STATE_ARTIFACT,
                    "expired": False,
                    "created_at": "2026-10-14T10:00:00Z",
                    "archive_download_url": "https://example.invalid/archive",
                }
            ]
        },
    )

    with pytest.raises(EvidenceError, match="provenance"):
        agent.prior_state("owner/repo", "token", "99")


def test_prior_state_rejects_corrupt_zip(monkeypatch) -> None:
    calls = 0

    def fake_request(url, token, binary=False):
        nonlocal calls
        calls += 1
        if binary:
            return b"not a zip archive"
        return {
            "artifacts": [
                {
                    "name": agent.STATE_ARTIFACT,
                    "expired": False,
                    "created_at": "2026-10-14T10:00:00Z",
                    "archive_download_url": "https://example.invalid/archive",
                    "workflow_run": {"id": 123, "head_repository_id": 1},
                }
            ]
        }

    monkeypatch.setattr(agent, "github_request", fake_request)

    with pytest.raises(EvidenceError, match="unreadable"):
        agent.prior_state("owner/repo", "token", "99")


def test_prior_state_rejects_invalid_json_inside_zip(monkeypatch) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("state.json", "{bad json")

    def fake_request(url, token, binary=False):
        if binary:
            return buffer.getvalue()
        return {
            "artifacts": [
                {
                    "name": agent.STATE_ARTIFACT,
                    "expired": False,
                    "created_at": "2026-10-14T10:00:00Z",
                    "archive_download_url": "https://example.invalid/archive",
                    "workflow_run": {"id": 123, "head_repository_id": 1},
                }
            ]
        }

    monkeypatch.setattr(agent, "github_request", fake_request)

    with pytest.raises(EvidenceError, match="unreadable"):
        agent.prior_state("owner/repo", "token", "99")


def test_prior_state_rejects_invalid_state_contract_in_zip(monkeypatch) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("state.json", json.dumps({"schema_version": "1.0"}))

    def fake_request(url, token, binary=False):
        if binary:
            return buffer.getvalue()
        return {
            "artifacts": [
                {
                    "name": agent.STATE_ARTIFACT,
                    "expired": False,
                    "created_at": "2026-10-14T10:00:00Z",
                    "archive_download_url": "https://example.invalid/archive",
                    "workflow_run": {"id": 123, "head_repository_id": 1},
                }
            ]
        }

    monkeypatch.setattr(agent, "github_request", fake_request)

    with pytest.raises(EvidenceError, match="saved_at"):
        agent.prior_state("owner/repo", "token", "99")
