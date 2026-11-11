"""Unit tests for the fail-closed G1 trusted-lineage verifier."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from scripts.g1_verify import (
    EXPECTED_ARTIFACT,
    EXPECTED_JOB_NAME,
    FROZEN_CORE_BLOB,
    VerificationError,
    verify_lineage,
)

PR_NUMBER = 42
HEAD_SHA = "a" * 40
RUN_ID = 123456
ZIP_SHA = "b" * 64


def _fixtures(
    *,
    status: str = "completed",
    conclusion: str = "success",
    evidence_overrides: dict[str, Any] | None = None,
    include_artifact: bool = True,
) -> tuple[Any, Any]:
    older = {
        "id": RUN_ID - 1,
        "created_at": "2026-11-10T10:00:00Z",
        "status": "completed",
        "conclusion": "success",
        "event": "pull_request",
        "path": ".github/workflows/research-loop-v0.yml",
        "head_sha": HEAD_SHA,
        "pull_requests": [{"number": PR_NUMBER}],
    }
    newest = {
        **older,
        "id": RUN_ID,
        "created_at": "2026-11-10T11:00:00Z",
        "status": status,
        "conclusion": conclusion,
    }
    evidence: dict[str, Any] = {
        "state": "VERIFIED",
        "scope": "PR",
        "workflow": "Research Loop v0 Gate",
        "run_id": str(RUN_ID),
        "job_id": "research-loop-gate",
        "status": "completed",
        "conclusion": "success",
        "target_sha": HEAD_SHA,
        "base_sha": "c" * 40,
        "pr_number": PR_NUMBER,
        "frozen_core_blob": FROZEN_CORE_BLOB,
    }
    if evidence_overrides:
        evidence.update(evidence_overrides)

    artifact = {
        "id": 987,
        "name": EXPECTED_ARTIFACT,
        "expired": False,
        "digest": f"sha256:{ZIP_SHA}",
        "archive_download_url": "https://api.github.com/artifacts/987/zip",
        "workflow_run": {"id": RUN_ID},
    }

    def api_get(path: str) -> dict[str, Any]:
        if "/actions/workflows/" in path:
            return {"workflow_runs": [older, newest]}
        if f"/actions/runs/{RUN_ID}/jobs" in path:
            return {
                "jobs": [{
                    "id": 456,
                    "run_id": RUN_ID,
                    "name": EXPECTED_JOB_NAME,
                    "status": "completed",
                    "conclusion": "success",
                    "head_sha": HEAD_SHA,
                }]
            }
        if f"/actions/runs/{RUN_ID}/artifacts" in path:
            return {"artifacts": [artifact] if include_artifact else []}
        raise AssertionError(f"Unexpected GitHub API path: {path}")

    def download(_artifact: dict[str, Any], _dest: str) -> tuple[str, dict[str, Any]]:
        return ZIP_SHA, evidence

    return api_get, download


def test_newest_run_success_with_valid_artifact_passes() -> None:
    api_get, download = _fixtures()
    result = verify_lineage(PR_NUMBER, HEAD_SHA, "qwertymarketolog-lab/JAMP", api_get, download)
    assert result["state"] == "VERIFIED"
    assert result["research_loop_run_id"] == RUN_ID
    assert result["research_loop_artifact_sha256"] == ZIP_SHA


def test_newest_run_failed_does_not_fall_back_to_older_success() -> None:
    api_get, download = _fixtures(conclusion="failure")
    with pytest.raises(VerificationError, match="newest_run_failed"):
        verify_lineage(PR_NUMBER, HEAD_SHA, "qwertymarketolog-lab/JAMP", api_get, download)


def test_newest_run_in_progress_does_not_fall_back_to_older_success() -> None:
    api_get, download = _fixtures(status="in_progress", conclusion=None)
    with pytest.raises(VerificationError, match="newest_run_not_terminal"):
        verify_lineage(PR_NUMBER, HEAD_SHA, "qwertymarketolog-lab/JAMP", api_get, download)


def test_artifact_missing_fails_closed() -> None:
    api_get, download = _fixtures(include_artifact=False)
    with pytest.raises(VerificationError, match="artifact_missing_or_duplicate"):
        verify_lineage(PR_NUMBER, HEAD_SHA, "qwertymarketolog-lab/JAMP", api_get, download)


def test_artifact_sha_mismatch_fails_closed() -> None:
    api_get, download = _fixtures()
    def bad_download(_artifact: dict[str, Any], _dest: str) -> tuple[str, dict[str, Any]]:
        return hashlib.sha256(b"different archive").hexdigest(), {
            "pr_number": PR_NUMBER,
        }
    with pytest.raises(VerificationError, match="artifact_sha256_mismatch"):
        verify_lineage(PR_NUMBER, HEAD_SHA, "qwertymarketolog-lab/JAMP", api_get, bad_download)


def test_evidence_pr_mismatch_fails_closed() -> None:
    api_get, download = _fixtures(evidence_overrides={"pr_number": PR_NUMBER + 1})
    with pytest.raises(VerificationError, match="evidence_validation_failed"):
        verify_lineage(PR_NUMBER, HEAD_SHA, "qwertymarketolog-lab/JAMP", api_get, download)


def test_frozen_core_mismatch_fails_closed() -> None:
    api_get, download = _fixtures(evidence_overrides={"frozen_core_blob": "0" * 40})
    with pytest.raises(VerificationError, match="evidence_validation_failed"):
        verify_lineage(PR_NUMBER, HEAD_SHA, "qwertymarketolog-lab/JAMP", api_get, download)
