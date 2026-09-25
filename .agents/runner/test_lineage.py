"""Tests for the G1 v1 lineage verification contract."""

from __future__ import annotations

from dataclasses import dataclass

from lineage import LineageResult, verify_lineage

SHA = "a" * 40
RUN = {
    "id": 36084358380,
    "workflow_id": 366569738,
    "path": ".github/workflows/research-loop-v0.yml",
    "event": "pull_request",
    "head_sha": SHA,
    "status": "completed",
    "conclusion": "success",
}
JOB = {
    "id": 107912825302,
    "run_id": 36084358380,
    "name": "research-loop-gate",
    "status": "completed",
    "conclusion": "success",
}


@dataclass
class FakeProvider:
    run: dict
    job: dict

    def get_run(self, repository: str, run_id: int) -> dict:
        return self.run

    def get_job(self, repository: str, job_id: int) -> dict:
        return self.job


def verify(provider: FakeProvider) -> LineageResult:
    return verify_lineage(
        provider=provider,
        repository="qwertymarketolog-lab/JAMP",
        run_id=36084358380,
        job_id=107912825302,
        expected_target_sha=SHA,
        expected_workflow_id=366569738,
        expected_workflow_path=".github/workflows/research-loop-v0.yml",
        expected_job_name="research-loop-gate",
    )


def test_valid_lineage_is_verified() -> None:
    result = verify(FakeProvider(RUN.copy(), JOB.copy()))
    assert result.verified
    assert result.reason == "verified"


def test_wrong_run_sha_is_inconclusive() -> None:
    run = RUN.copy()
    run["head_sha"] = "b" * 40
    assert not verify(FakeProvider(run, JOB.copy())).verified


def test_wrong_workflow_is_inconclusive() -> None:
    run = RUN.copy()
    run["workflow_id"] = 1
    assert not verify(FakeProvider(run, JOB.copy())).verified


def test_wrong_event_is_inconclusive() -> None:
    run = RUN.copy()
    run["event"] = "push"
    assert not verify(FakeProvider(run, JOB.copy())).verified


def test_failed_run_is_inconclusive() -> None:
    run = RUN.copy()
    run["conclusion"] = "failure"
    assert not verify(FakeProvider(run, JOB.copy())).verified


def test_wrong_job_id_is_inconclusive() -> None:
    job = JOB.copy()
    job["id"] = 999
    assert not verify(FakeProvider(RUN.copy(), job)).verified


def test_job_from_other_run_is_inconclusive() -> None:
    job = JOB.copy()
    job["run_id"] = 999
    assert not verify(FakeProvider(RUN.copy(), job)).verified


def test_wrong_job_name_is_inconclusive() -> None:
    job = JOB.copy()
    job["name"] = "other-job"
    assert not verify(FakeProvider(RUN.copy(), job)).verified


def test_failed_job_is_inconclusive() -> None:
    job = JOB.copy()
    job["conclusion"] = "failure"
    assert not verify(FakeProvider(RUN.copy(), job)).verified


def test_api_error_is_inconclusive() -> None:
    class BrokenProvider(FakeProvider):
        def get_run(self, repository: str, run_id: int) -> dict:
            raise RuntimeError("API unavailable")

    assert not verify(BrokenProvider(RUN.copy(), JOB.copy())).verified


def test_malformed_run_is_inconclusive() -> None:
    assert not verify(FakeProvider({"id": 36084358380}, JOB.copy())).verified


def test_invalid_input_is_inconclusive() -> None:
    result = verify_lineage(
        provider=FakeProvider(RUN.copy(), JOB.copy()),
        repository="qwertymarketolog-lab/JAMP",
        run_id=0,
        job_id=107912825302,
        expected_target_sha=SHA,
        expected_workflow_id=366569738,
        expected_workflow_path=".github/workflows/research-loop-v0.yml",
        expected_job_name="research-loop-gate",
    )
    assert not result.verified
    assert result.reason == "invalid_verification_input"


def test_local_claim_cannot_escalate_trust() -> None:
    provider = FakeProvider(RUN.copy(), JOB.copy())
    result = verify(provider)
    assert result.verified is True
    assert result.target_sha == SHA
