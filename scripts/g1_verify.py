"""Fail-closed verifier for PR trusted-lineage evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
RESEARCH_LOOP_WORKFLOW = "research-loop-v0.yml"
EXPECTED_ARTIFACT = "research-loop-v0-evidence"
EXPECTED_EVIDENCE_FILE = "research-loop-evidence.json"
EXPECTED_JOB_NAME = "Research Loop v0 Gate /"
EXPECTED_WORKFLOW_JOB_ID = "research-loop-gate"
ALLOWED_HOSTS = {"api.github.com", "objects.githubusercontent.com", "github.com"}
ALLOWED_SUFFIXES = (".blob.core.windows.net",)
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024
MAX_ENTRIES = 100
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_EVIDENCE_BYTES = 1 * 1024 * 1024


def _allowed_https_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    try:
        standard_port = parsed.port in (None, 443)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and standard_port
        and (host in ALLOWED_HOSTS or any(host.endswith(suffix) for suffix in ALLOWED_SUFFIXES))
    )


class VerificationError(RuntimeError):
    """Raised when trusted-lineage evidence is absent or invalid."""


def gh_api(path: str) -> dict[str, Any]:
    token = os.environ["GITHUB_TOKEN"]
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=30) as response:
        if (
            not _allowed_https_url(response.geturl())
            or urlparse(response.geturl()).hostname != "api.github.com"
        ):
            raise VerificationError("github_api_final_url_invalid")
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise VerificationError("github_api_invalid_response")
    return payload


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request: Any, response: Any, code: int,
                         message: str, headers: Any, new_url: str) -> None:
        return None


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Allow only known GitHub artifact hosts and never forward credentials."""

    def redirect_request(self, request: Any, response: Any, code: int,
                         message: str, headers: Any, new_url: str) -> Any:
        if not _allowed_https_url(new_url):
            host = (urlparse(new_url).hostname or "").lower()
            raise urllib.error.HTTPError(
                new_url, code, f"redirect_to_disallowed_host: {host}", headers, response
            )
        # A redirect is a new unauthenticated GET. In particular, never copy
        # Authorization or other caller-controlled headers to the storage host.
        return urllib.request.Request(
            new_url,
            headers={"Accept": "application/octet-stream"},
            method="GET",
        )


POLL_INTERVAL_SECONDS = 10
TERMINAL_TIMEOUT_SECONDS = 300


def wait_for_terminal(
    run_id: int,
    api_get: Callable[[str], dict[str, Any]] | None = None,
    timeout_seconds: int = TERMINAL_TIMEOUT_SECONDS,
    poll_interval: int = POLL_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Wait for a GitHub Actions run to reach a verified terminal success.

    API errors propagate unchanged. Non-success terminal conclusions and timeout
    fail closed; successful runs are returned for downstream job/artifact checks.
    """
    if run_id <= 0:
        raise VerificationError("research_loop_run_id_invalid")
    if timeout_seconds < 0 or poll_interval <= 0:
        raise ValueError("timeout_seconds must be non-negative and poll_interval positive")

    get_run = gh_api if api_get is None else api_get
    deadline = time.monotonic() + timeout_seconds
    first_poll = True
    last_status: Any = None

    while first_poll or time.monotonic() < deadline:
        first_poll = False
        run = get_run(f"/repos/{REPO}/actions/runs/{run_id}")
        if not isinstance(run, dict):
            raise VerificationError("newest_run_response_invalid")

        last_status = run.get("status")
        conclusion = run.get("conclusion")
        if last_status == "completed":
            if conclusion == "success":
                return run
            if conclusion in {"failure", "cancelled"}:
                raise VerificationError(f"newest_run_{conclusion}")
            raise VerificationError(f"newest_run_{conclusion or 'unknown'}")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(poll_interval, remaining))

    raise VerificationError(
        f"newest_run_timeout: last_status={last_status} "
        f"after {timeout_seconds}s"
    )


def _download_url(url: str, destination: Path) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "api.github.com":
        raise VerificationError("artifact_download_url_invalid")

    token = os.environ["GITHUB_TOKEN"]
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    opener = urllib.request.build_opener(SafeRedirectHandler())
    with opener.open(request, timeout=30) as response:
        final_url = response.geturl()
        if not _allowed_https_url(final_url):
            final_host = (urlparse(final_url).hostname or "").lower()
            raise VerificationError(f"artifact_final_url_disallowed: {final_host}")
        downloaded = 0
        with destination.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                downloaded += len(chunk)
                if downloaded > MAX_ARTIFACT_BYTES:
                    raise VerificationError("artifact_archive_too_large")
                output.write(chunk)


def download_artifact(artifact: dict[str, Any], dest: str) -> tuple[str, dict[str, Any]]:
    archive_url = artifact.get("archive_download_url")
    if not isinstance(archive_url, str):
        raise VerificationError("artifact_archive_url_missing")

    archive = Path(dest)
    _download_url(archive_url, archive)
    if archive.stat().st_size > MAX_ARTIFACT_BYTES:
        raise VerificationError("artifact_archive_too_large")
    digest = hashlib.sha256()
    with archive.open("rb") as downloaded:
        while chunk := downloaded.read(1024 * 1024):
            digest.update(chunk)
    zip_sha256 = digest.hexdigest()

    try:
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if len(entries) > MAX_ENTRIES:
                raise VerificationError("artifact_too_many_entries")
            total_uncompressed = sum(item.file_size for item in entries)
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise VerificationError("artifact_uncompressed_size_limit_exceeded")
            files = [item for item in entries if not item.is_dir()]
            if len(files) != 1 or files[0].filename != EXPECTED_EVIDENCE_FILE:
                raise VerificationError("artifact_file_set_invalid")
            if files[0].file_size > MAX_EVIDENCE_BYTES:
                raise VerificationError("artifact_evidence_too_large")
            with bundle.open(files[0]) as evidence_file:
                raw = evidence_file.read(MAX_EVIDENCE_BYTES + 1)
            if len(raw) > MAX_EVIDENCE_BYTES:
                raise VerificationError("artifact_evidence_too_large")
            evidence = json.loads(raw)
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as error:
        raise VerificationError("artifact_evidence_malformed") from error

    if not isinstance(evidence, dict):
        raise VerificationError("artifact_evidence_not_object")
    return zip_sha256, evidence


def _all_workflow_runs(api_get: Callable[[str], dict[str, Any]],
                       repo: str, head_sha: str) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = api_get(
            f"/repos/{repo}/actions/workflows/{RESEARCH_LOOP_WORKFLOW}/runs"
            f"?head_sha={head_sha}&event=pull_request&per_page=100&page={page}"
        )
        page_runs = payload.get("workflow_runs")
        if not isinstance(page_runs, list):
            raise VerificationError("workflow_runs_response_invalid")
        runs.extend(run for run in page_runs if isinstance(run, dict))
        if len(page_runs) < 100:
            return runs
        page += 1


def verify_lineage(
    pr_number: int,
    head_sha: str,
    repo: str,
    api_get: Callable[[str], dict[str, Any]] = gh_api,
    artifact_downloader: Callable[
        [dict[str, Any], str], tuple[str, dict[str, Any]]
    ] = download_artifact,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", head_sha):
        raise VerificationError("head_sha_invalid")
    if pr_number < 1 or repo != "qwertymarketolog-lab/JAMP":
        raise VerificationError("repository_or_pr_invalid")

    runs = _all_workflow_runs(api_get, repo, head_sha)
    pr_runs = [
        run for run in runs
        if run.get("event") == "pull_request"
        and run.get("path", "").endswith(f"/{RESEARCH_LOOP_WORKFLOW}")
        and run.get("head_sha") == head_sha
        and any(
            isinstance(pr, dict) and pr.get("number") == pr_number
            for pr in run.get("pull_requests", [])
        )
    ]
    if not pr_runs:
        raise VerificationError("no_research_loop_runs_for_pr_head")

    newest = max(
        pr_runs,
        key=lambda run: (run.get("created_at", ""), run.get("id", 0)),
    )
    run_id = newest.get("id")
    if not isinstance(run_id, int):
        raise VerificationError("research_loop_run_id_invalid")
    terminal_run = wait_for_terminal(run_id, api_get=api_get)

    jobs_payload = api_get(
        f"/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"
    )
    jobs = jobs_payload.get("jobs")
    if not isinstance(jobs, list):
        raise VerificationError("research_loop_jobs_invalid")
    matching_jobs = [
        job for job in jobs
        if isinstance(job, dict) and job.get("name") == EXPECTED_JOB_NAME
    ]
    if len(matching_jobs) != 1:
        raise VerificationError("research_loop_expected_job_missing_or_duplicate")
    job = matching_jobs[0]
    if not isinstance(job.get("id"), int) or job["id"] <= 0:
        raise VerificationError("research_loop_numeric_job_id_invalid")
    if (
        job.get("run_id") != run_id
        or job.get("status") != "completed"
        or job.get("conclusion") != "success"
        or job.get("head_sha") != head_sha
    ):
        raise VerificationError("research_loop_job_not_verified")

    artifacts_payload = api_get(
        f"/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    )
    artifacts = artifacts_payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise VerificationError("research_loop_artifacts_invalid")
    matches = [
        artifact for artifact in artifacts
        if isinstance(artifact, dict) and artifact.get("name") == EXPECTED_ARTIFACT
    ]
    if len(matches) != 1:
        raise VerificationError("research_loop_artifact_missing_or_duplicate")
    artifact = matches[0]
    if artifact.get("expired") is not False:
        raise VerificationError("research_loop_artifact_expired_or_unknown")
    workflow_run = artifact.get("workflow_run")
    if not isinstance(workflow_run, dict):
        raise VerificationError("artifact_workflow_run_missing_or_invalid")
    if workflow_run.get("id") != run_id:
        raise VerificationError("research_loop_artifact_run_mismatch")

    zip_sha256, evidence = artifact_downloader(artifact, "/tmp/research-loop.zip")
    expected_digest = artifact.get("digest")
    if not isinstance(expected_digest, str) or expected_digest != f"sha256:{zip_sha256}":
        raise VerificationError("research_loop_artifact_sha256_mismatch")

    expected = {
        "pr_number": pr_number,
        "target_sha": head_sha,
        "run_id": str(run_id),
        "job_id": EXPECTED_WORKFLOW_JOB_ID,
        "status": "completed",
        "conclusion": "success",
        "frozen_core_blob": FROZEN_CORE_BLOB,
    }
    failed = [
        key for key, value in expected.items()
        if evidence.get(key) != value
    ]
    if failed:
        raise VerificationError(f"evidence_validation_failed: {failed}")

    own = {
        "state": "VERIFIED",
        "pr_number": pr_number,
        "target_sha": head_sha,
        "research_loop_run_id": run_id,
        "research_loop_job_id": job.get("id"),
        "research_loop_job_name": job.get("name"),
        "research_loop_artifact_id": artifact.get("id"),
        "research_loop_artifact_name": EXPECTED_ARTIFACT,
        "research_loop_artifact_sha256": zip_sha256,
        "frozen_core_blob": FROZEN_CORE_BLOB,
        "checks": {key: True for key in expected},
    }
    return own


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    github_run_id = os.environ.get("GITHUB_RUN_ID")
    try:
        if not github_run_id:
            raise VerificationError("github_run_id_missing")
        evidence = verify_lineage(
            args.pr_number,
            args.head_sha,
            os.environ["GITHUB_REPOSITORY"],
        )
        success = {
            "status": "VERIFIED",
            **evidence,
            "verified_at_run_id": github_run_id,
        }
        output.write_text(
            json.dumps(success, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        digest = hashlib.sha256(
            json.dumps(success, sort_keys=True).encode("utf-8")
        ).hexdigest()
        print(f"G1_VERIFIED: evidence_sha256={digest}")
    except Exception as error:
        failure = {
            "status": "FAIL",
            "reason": str(error) or error.__class__.__name__,
            "pr_number": args.pr_number,
            "head_sha": args.head_sha,
            "verified_at_run_id": github_run_id,
        }
        try:
            output.write_text(
                json.dumps(failure, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as write_error:
            print(
                f"G1_FAIL: {failure['reason']}; failure_evidence_write_failed: {write_error}",
                file=sys.stderr,
            )
            raise SystemExit(1) from write_error
        print(f"G1_FAIL: {failure['reason']}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
