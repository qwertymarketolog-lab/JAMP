from decision import Decision
from gate import evaluate_gate
from provenance import LOCKED_CORE_BLOB, CICheck, ProvenanceEvidence
from task_loader import TaskContract

BASE = "6b066b282e7727a6bb01de33e64ce39df96f8d8c"
TARGET = "2c836157267ce08626ff3ebdbde37e22d7d1c3f8"
TASK = TaskContract(
    "TASK-002",
    1,
    (".agents/runner/**",),
    ("src/jamp/**",),
    "main",
    BASE,
    True,
)


def evidence(checks=()):
    return ProvenanceEvidence(
        task_id="TASK-002",
        source_sha=BASE,
        target_sha=TARGET,
        base_ref="main",
        branch="agent/test",
        pr_number=173,
        changed_paths=(".agents/runner/gate.py",),
        ci_checks=tuple(checks),
        frozen_core_blob=LOCKED_CORE_BLOB,
    )


def ok_check():
    return CICheck("quality", "100", "200", "completed", "success")


def test_allow_requires_complete_provenance_and_ci():
    assert evaluate_gate(
        task=TASK,
        evidence=evidence((ok_check(),)),
        expected_source_sha=BASE,
        expected_target_sha=TARGET,
        required_workflows=("quality",),
    ) is Decision.ALLOW


def test_missing_jobs_is_inconclusive():
    assert evaluate_gate(
        task=TASK,
        evidence=evidence(()),
        expected_source_sha=BASE,
        expected_target_sha=TARGET,
        required_workflows=("quality",),
    ) is Decision.INCONCLUSIVE


def test_failed_ci_is_reject():
    failed = CICheck("quality", "100", "200", "completed", "failure")
    assert evaluate_gate(
        task=TASK,
        evidence=evidence((failed,)),
        expected_source_sha=BASE,
        expected_target_sha=TARGET,
        required_workflows=("quality",),
    ) is Decision.REJECT


def test_nonterminal_ci_is_inconclusive():
    pending = CICheck("quality", "100", "200", "in_progress", "")
    assert evaluate_gate(
        task=TASK,
        evidence=evidence((pending,)),
        expected_source_sha=BASE,
        expected_target_sha=TARGET,
        required_workflows=("quality",),
    ) is Decision.REJECT


def test_path_violation_is_reject():
    bad = ProvenanceEvidence(
        **{**evidence((ok_check(),)).__dict__, "changed_paths": ("src/jamp/run.py",)}
    )
    assert evaluate_gate(
        task=TASK,
        evidence=bad,
        expected_source_sha=BASE,
        expected_target_sha=TARGET,
        required_workflows=("quality",),
    ) is Decision.REJECT


def test_core_blob_mismatch_is_reject():
    bad = ProvenanceEvidence(
        **{**evidence((ok_check(),)).__dict__, "frozen_core_blob": "wrong"}
    )
    assert evaluate_gate(
        task=TASK,
        evidence=bad,
        expected_source_sha=BASE,
        expected_target_sha=TARGET,
        required_workflows=("quality",),
    ) is Decision.REJECT


def test_source_or_target_mismatch_is_inconclusive():
    bad = ProvenanceEvidence(
        **{**evidence((ok_check(),)).__dict__, "target_sha": BASE}
    )
    assert evaluate_gate(
        task=TASK,
        evidence=bad,
        expected_source_sha=BASE,
        expected_target_sha=TARGET,
        required_workflows=("quality",),
    ) is Decision.INCONCLUSIVE
