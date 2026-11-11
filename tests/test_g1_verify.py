"""Unit tests for the fail-closed G1 trusted-lineage verifier."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any

import pytest

import scripts.g1_verify as verifier
from scripts.g1_verify import (
    download_artifact,
    main,
    EXPECTED_ARTIFACT,
    EXPECTED_JOB_NAME,
    FROZEN_CORE_BLOB,
    SafeRedirectHandler,
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



def test_redirect_to_evil_host_rejected() -> None:
    from urllib.error import HTTPError
    from urllib.request import Request

    handler = SafeRedirectHandler()
    request = Request("https://api.github.com/artifact", headers={"Authorization": "Bearer secret"})
    with pytest.raises(HTTPError, match="redirect_to_disallowed_host"):
        handler.redirect_request(
            request, None, 302, "Found", {}, "https://evil.com/steal"
        )


def test_evidence_job_id_uses_actual_workflow_key() -> None:
    api_get, download = _fixtures()
    result = verify_lineage(PR_NUMBER, HEAD_SHA, "qwertymarketolog-lab/JAMP", api_get, download)
    assert result["research_loop_job_id"] == 456
    assert result["research_loop_job_name"] == EXPECTED_JOB_NAME


def test_evidence_job_id_mismatch_fails_closed() -> None:
    api_get, download = _fixtures(evidence_overrides={"job_id": 456})
    with pytest.raises(VerificationError, match="evidence_validation_failed"):
        verify_lineage(PR_NUMBER, HEAD_SHA, "qwertymarketolog-lab/JAMP", api_get, download)


def test_job_missing_from_run_fails_closed() -> None:
    api_get, download = _fixtures()
    def missing_job(path: str) -> dict[str, Any]:
        payload = api_get(path)
        if f"/actions/runs/{RUN_ID}/jobs" in path:
            return {"jobs": []}
        return payload
    with pytest.raises(VerificationError, match="expected_job_missing_or_duplicate"):
        verify_lineage(PR_NUMBER, HEAD_SHA, "qwertymarketolog-lab/JAMP", missing_job, download)



def test_allowed_artifact_redirect_does_not_forward_authorization() -> None:
    from urllib.request import Request

    handler = SafeRedirectHandler()
    request = Request(
        "https://api.github.com/artifact",
        headers={"Authorization": "Bearer secret", "X-Custom": "private"},
    )
    redirected = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://objects.githubusercontent.com/signed/archive.zip",
    )
    assert redirected is not None
    assert redirected.full_url == "https://objects.githubusercontent.com/signed/archive.zip"
    redirected_headers = {key.lower() for key, _ in redirected.header_items()}
    assert "authorization" not in redirected_headers
    assert "x-custom" not in redirected_headers


def test_blob_suffix_requires_dot_boundary() -> None:
    from urllib.error import HTTPError
    from urllib.request import Request

    handler = SafeRedirectHandler()
    request = Request("https://api.github.com/artifact")
    with pytest.raises(HTTPError, match="redirect_to_disallowed_host"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://evilblob.core.windows.net/archive.zip",
        )



def test_zip_entry_count_limit_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "artifact.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("research-loop-evidence.json", "{}")
        bundle.writestr("extra.txt", "unexpected")
    monkeypatch.setattr(verifier, "_download_url", lambda _url, destination: destination.write_bytes(archive.read_bytes()))
    monkeypatch.setattr(verifier, "MAX_ENTRIES", 1)
    with pytest.raises(VerificationError, match="artifact_too_many_entries"):
        download_artifact({"archive_download_url": "https://api.github.com/artifacts/1/zip"}, str(tmp_path / "download.zip"))


def test_artifact_download_byte_limit_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verifier, "MAX_ARTIFACT_BYTES", 4)
    monkeypatch.setattr(verifier, "_download_url", lambda _url, destination: destination.write_bytes(b"12345"))
    with pytest.raises(VerificationError, match="artifact_archive_too_large"):
        download_artifact({"archive_download_url": "https://api.github.com/artifacts/1/zip"}, str(tmp_path / "download.zip"))


def test_missing_github_run_id_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["g1_verify.py", "--pr-number", "42", "--head-sha", "a" * 40, "--output", "out.json"])
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert "github_run_id_missing" in capsys.readouterr().err
