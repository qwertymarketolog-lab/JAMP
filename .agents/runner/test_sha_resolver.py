from decision import Decision
from sha_resolver import resolve_base_sha
from task_loader import TaskValidationError, load_task

SHA_A = "0" * 40
SHA_B = "1" * 40


def test_base_ref_resolves_and_matches() -> None:
    result = resolve_base_sha(
        base_ref="main",
        expected_base_sha=SHA_A,
        require_head_match=True,
        ref_resolver=lambda ref: SHA_A,
    )
    assert result.decision is Decision.ALLOW
    assert result.resolved_sha == SHA_A


def test_base_ref_mismatch_is_inconclusive() -> None:
    result = resolve_base_sha(
        base_ref="main",
        expected_base_sha=SHA_A,
        require_head_match=True,
        ref_resolver=lambda ref: SHA_B,
    )
    assert result.decision is Decision.INCONCLUSIVE
    assert result.resolved_sha == SHA_B


def test_missing_expected_sha_is_inconclusive_when_required() -> None:
    result = resolve_base_sha(
        base_ref="main",
        expected_base_sha=None,
        require_head_match=True,
        ref_resolver=lambda ref: SHA_A,
    )
    assert result.decision is Decision.INCONCLUSIVE


def test_invalid_resolved_sha_is_inconclusive() -> None:
    result = resolve_base_sha(
        base_ref="main",
        expected_base_sha=SHA_A,
        require_head_match=True,
        ref_resolver=lambda ref: "not-a-sha",
    )
    assert result.decision is Decision.INCONCLUSIVE


def test_resolver_exception_fails_closed() -> None:
    def fail(_: str) -> str:
        raise RuntimeError("boom")

    result = resolve_base_sha(
        base_ref="main",
        expected_base_sha=SHA_A,
        require_head_match=True,
        ref_resolver=fail,
    )
    assert result.decision is Decision.INCONCLUSIVE
    assert result.resolved_sha is None


def test_task_source_contract() -> None:
    task = load_task(
        f"""task_id: TASK-002
version: 1
source:
  base_ref: "main"
  expected_base_sha: "{SHA_A}"
  require_head_match: true
scope:
  allowed_paths:
    - ".agents/runner/**"
  forbidden_paths:
    - "src/jamp/**"
"""
    )
    assert task.base_ref == "main"
    assert task.expected_base_sha == SHA_A
    assert task.require_head_match is True


def test_task_rejects_required_head_match_without_expected_sha() -> None:
    try:
        load_task(
            """task_id: TASK-002
version: 1
source:
  base_ref: "main"
  require_head_match: true
scope:
  allowed_paths:
    - ".agents/runner/**"
  forbidden_paths:
    - "src/jamp/**"
"""
        )
    except TaskValidationError:
        return
    raise AssertionError("missing expected_base_sha was accepted")
