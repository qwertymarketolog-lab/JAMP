"""Fail-closed GitHub Actions lineage verification contract for G1 v1."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from typing import Protocol

_SHA_LENGTH = 40


@dataclass(frozen=True)
class LineageResult:
    """Immutable result of independent run/job lineage verification."""

    verified: bool
    reason: str
    run_id: int | None
    job_id: int | None
    target_sha: str | None
    workflow_id: int | None
    workflow_path: str | None
    event: str | None
    run_status: str | None
    run_conclusion: str | None
    job_name: str | None
    job_status: str | None
    job_conclusion: str | None


class LineageProvider(Protocol):
    """Trusted provider of GitHub Actions run and job observations."""

    def get_run(self, repository: str, run_id: int) -> Mapping[str, object]:
        """Return the externally observed workflow-run payload."""

    def get_job(self, repository: str, job_id: int) -> Mapping[str, object]:
        """Return the externally observed workflow-job payload."""


def _inconclusive(
    *,
    reason: str,
    run_id: int | None = None,
    job_id: int | None = None,
    target_sha: str | None = None,
    run: Mapping[str, object] | None = None,
    job: Mapping[str, object] | None = None,
) -> LineageResult:
    return LineageResult(
        verified=False,
        reason=reason,
        run_id=run_id,
        job_id=job_id,
        target_sha=target_sha,
        workflow_id=_as_int(run, "workflow_id"),
        workflow_path=_as_str(run, "path"),
        event=_as_str(run, "event"),
        run_status=_as_str(run, "status"),
        run_conclusion=_as_str(run, "conclusion"),
        job_name=_as_str(job, "name"),
        job_status=_as_str(job, "status"),
        job_conclusion=_as_str(job, "conclusion"),
    )


def _as_int(payload: Mapping[str, object] | None, key: str) -> int | None:
    if payload is None:
        return None
    value = payload.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_str(payload: Mapping[str, object] | None, key: str) -> str | None:
    if payload is None:
        return None
    value = payload.get(key)
    return value if isinstance(value, str) else None


def verify_lineage(
    *,
    provider: LineageProvider,
    repository: str,
    run_id: int,
    job_id: int,
    expected_target_sha: str,
    expected_workflow_id: int,
    expected_workflow_path: str,
    expected_job_name: str,
    expected_event: str = "pull_request",
) -> LineageResult:
    """Verify GitHub run/job lineage; every failure is fail-closed."""
    if (
        not repository
        or run_id <= 0
        or job_id <= 0
        or len(expected_target_sha) != _SHA_LENGTH
        or any(c not in "0123456789abcdef" for c in expected_target_sha.lower())
        or expected_workflow_id <= 0
        or not expected_workflow_path
        or not expected_job_name
        or not expected_event
    ):
        return _inconclusive(
            reason="invalid_verification_input",
            run_id=run_id if run_id > 0 else None,
            job_id=job_id if job_id > 0 else None,
            target_sha=expected_target_sha or None,
        )

    try:
        run = provider.get_run(repository, run_id)
        job = provider.get_job(repository, job_id)
    except Exception:
        return _inconclusive(
            reason="external_api_error",
            run_id=run_id,
            job_id=job_id,
            target_sha=expected_target_sha,
        )

    required_run = (
        _as_int(run, "id") == run_id
        and _as_int(run, "workflow_id") == expected_workflow_id
        and _as_str(run, "path") == expected_workflow_path
        and _as_str(run, "event") == expected_event
        and _as_str(run, "head_sha") == expected_target_sha
        and _as_str(run, "status") == "completed"
        and _as_str(run, "conclusion") == "success"
    )
    if not required_run:
        return _inconclusive(
            reason="run_lineage_mismatch",
            run_id=run_id,
            job_id=job_id,
            target_sha=expected_target_sha,
            run=run,
            job=job,
        )

    required_job = (
        _as_int(job, "id") == job_id
        and _as_int(job, "run_id") == run_id
        and _as_str(job, "name") == expected_job_name
        and _as_str(job, "status") == "completed"
        and _as_str(job, "conclusion") == "success"
    )
    if not required_job:
        return _inconclusive(
            reason="job_lineage_mismatch",
            run_id=run_id,
            job_id=job_id,
            target_sha=expected_target_sha,
            run=run,
            job=job,
        )

    return LineageResult(
        verified=True,
        reason="verified",
        run_id=run_id,
        job_id=job_id,
        target_sha=expected_target_sha,
        workflow_id=expected_workflow_id,
        workflow_path=expected_workflow_path,
        event=expected_event,
        run_status="completed",
        run_conclusion="success",
        job_name=expected_job_name,
        job_status="completed",
        job_conclusion="success",
    )
