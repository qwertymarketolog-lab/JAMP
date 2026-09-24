"""Acceptance matrix for E1-E3 operation authorization."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from decision import Decision
from evidence import Evidence
from operation_policy import (
    Actor,
    Operation,
    Target,
    TargetKind,
    authorize_operation,
    evaluate_operation,
)
from mutation_adapter import apply

#
from task_loader import TaskContract


SOURCE_SHA = "TEST-SHA"


@dataclass(frozen=True)
class Case:
    test_id: str
    actor: Actor | str
    operation: Operation | str
    target: Target
    task: TaskContract
    evidence: Evidence | None
    expected: Decision
    attempts: int
    stage: str


def evidence(task_id: str = "TASK-001") -> Evidence:
    return Evidence(source_sha=SOURCE_SHA, task_id=task_id)


@pytest.fixture
def task() -> TaskContract:
    return TaskContract(
        task_id="TASK-001",
        version=1,
        allowed_paths=(
            ".agents/tasks/**",
            ".agents/state/**",
            ".agents/runner/**",
        ),
        forbidden_paths=("src/jamp/**",),
    )


@pytest.fixture
def e3_forbidden_task() -> TaskContract:
    return TaskContract(
        task_id="TASK-E3-001",
        version=1,
        allowed_paths=(".agents/runner/**",),
        forbidden_paths=(".agents/runner/blocked.py",),
    )


@pytest.fixture
def core_read_task() -> TaskContract:
    return TaskContract(
        task_id="TASK-CORE-READ",
        version=1,
        allowed_paths=("src/jamp/**",),
        forbidden_paths=(),
    )


def _path(value: str) -> Target:
    return Target(TargetKind.PATH, value)


def _ref(value: str) -> Target:
    return Target(TargetKind.REF, value)


def _run(case: Case) -> dict[str, object]:
    observed = evaluate_operation(
        actor=case.actor,
        operation=case.operation,
        target=case.target,
        task=case.task,
        evidence=case.evidence,
    )
    decision_match = observed is case.expected
    mutation_attempts = 0

    if observed is Decision.ALLOW and case.attempts:
        decision, authorization = authorize_operation(
            actor=case.actor,
            operation=case.operation,
            target=case.target,
            task=case.task,
            evidence=case.evidence,
        )
        assert decision is Decision.ALLOW
        assert authorization is not None
        result = apply(authorization)
        mutation_attempts = int(result.attempted)

    if observed is Decision.ALLOW and case.operation is Operation.READ:
        mutation_attempts = 0

    terminal_state = "VERIFIED" if decision_match else "CONTRACT_VIOLATION"
    return {
        "test_id": case.test_id,
        "source_sha": case.evidence.source_sha if case.evidence else SOURCE_SHA,
        "task_id": case.task.task_id,
        "actor": str(case.actor),
        "operation": str(case.operation),
        "target": {"kind": str(case.target.kind), "value": case.target.value},
        "evidence_present": case.evidence is not None,
        "expected_decision": str(case.expected),
        "observed_decision": str(observed),
        "decision_match": decision_match,
        "mutation_attempts": mutation_attempts,
        "policy_stage": case.stage,
        "policy_reason": case.stage,
        "terminal_state": terminal_state,
    }


def _assert_case(case: Case) -> None:
    record = _run(case)
    assert record["decision_match"] is True
    assert record["mutation_attempts"] == case.attempts


def test_v_a01_unknown_actor(task: TaskContract) -> None:
    _assert_case(
        Case(
            "V-A01",
            "unknown",
            Operation.WRITE,
            _path(".agents/runner/x.py"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P0_ACTOR",
        )
    )


def test_v_a02_unknown_actor_main_push(task: TaskContract) -> None:
    _assert_case(
        Case(
            "V-A02",
            "unknown",
            Operation.PUSH,
            _ref("main"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P0_ACTOR",
        )
    )


def test_v_o01_unknown_operation(task: TaskContract) -> None:
    _assert_case(
        Case(
            "V-O01",
            Actor.AGENT,
            "UNKNOWN",
            _path(".agents/runner/x.py"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P1_OPERATION",
        )
    )


def test_v_t01_write_ref_mismatch(task: TaskContract) -> None:
    _assert_case(
        Case(
            "V-T01",
            Actor.AGENT,
            Operation.WRITE,
            _ref("feature"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P2_TARGET_KIND",
        )
    )


def test_v_t02_push_path_mismatch(task: TaskContract) -> None:
    _assert_case(
        Case(
            "V-T02",
            Actor.AGENT,
            Operation.PUSH,
            _path(".agents/runner/x.py"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P2_TARGET_KIND",
        )
    )


def test_v_t03_invalid_target(task: TaskContract) -> None:
    _assert_case(
        Case(
            "V-T03",
            Actor.AGENT,
            Operation.WRITE,
            Target("BAD", "x"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P2_TARGET_KIND",
        )
    )


def test_e1_a01_agent_push_main_with_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E1-A01",
            Actor.AGENT,
            Operation.PUSH,
            _ref("main"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P4_E1_MAIN_BOUNDARY",
        )
    )


def test_e1_a02_agent_merge_main_with_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E1-A02",
            Actor.AGENT,
            Operation.MERGE,
            _ref("main"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P4_E1_MAIN_BOUNDARY",
        )
    )


def test_e1_a03_agent_push_main_without_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E1-A03",
            Actor.AGENT,
            Operation.PUSH,
            _ref("main"),
            task,
            None,
            Decision.REJECT,
            0,
            "P4_E1_MAIN_BOUNDARY",
        )
    )


def test_e1_a04_human_merge_main_without_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E1-A04",
            Actor.HUMAN,
            Operation.MERGE,
            _ref("main"),
            task,
            None,
            Decision.REJECT,
            0,
            "P4_E1_MAIN_BOUNDARY",
        )
    )


def test_e1_p01_agent_push_feature_with_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E1-P01",
            Actor.AGENT,
            Operation.PUSH,
            _ref("feature"),
            task,
            evidence(),
            Decision.ALLOW,
            1,
            "P9_ALLOW",
        )
    )


def test_e1_p02_agent_push_feature_without_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E1-P02",
            Actor.AGENT,
            Operation.PUSH,
            _ref("feature"),
            task,
            None,
            Decision.INCONCLUSIVE,
            0,
            "P7_EVIDENCE",
        )
    )


def test_e2_a01_agent_write_core_with_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E2-A01",
            Actor.AGENT,
            Operation.WRITE,
            _path("src/jamp/run.py"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P5_E2_FROZEN_CORE",
        )
    )


def test_e2_a02_agent_write_core_without_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E2-A02",
            Actor.AGENT,
            Operation.WRITE,
            _path("src/jamp/run.py"),
            task,
            None,
            Decision.REJECT,
            0,
            "P5_E2_FROZEN_CORE",
        )
    )


def test_e2_a03_agent_delete_core_with_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E2-A03",
            Actor.AGENT,
            Operation.DELETE,
            _path("src/jamp/run.py"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P5_E2_FROZEN_CORE",
        )
    )


def test_e2_a04_agent_delete_core_without_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E2-A04",
            Actor.AGENT,
            Operation.DELETE,
            _path("src/jamp/run.py"),
            task,
            None,
            Decision.REJECT,
            0,
            "P5_E2_FROZEN_CORE",
        )
    )


def test_e2_a05_core_traversal(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E2-A05",
            Actor.AGENT,
            Operation.WRITE,
            _path("../src/jamp/run.py"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P3_TARGET_STRUCTURE",
        )
    )


def test_e2_p01_agent_read_core_with_evidence(core_read_task: TaskContract) -> None:
    _assert_case(
        Case(
            "E2-P01",
            Actor.AGENT,
            Operation.READ,
            _path("src/jamp/run.py"),
            core_read_task,
            evidence("TASK-CORE-READ"),
            Decision.ALLOW,
            0,
            "P9_ALLOW",
        )
    )


def test_e3_a01_forbidden_path(e3_forbidden_task: TaskContract) -> None:
    _assert_case(
        Case(
            "E3-A01",
            Actor.AGENT,
            Operation.WRITE,
            _path(".agents/runner/blocked.py"),
            e3_forbidden_task,
            evidence("TASK-E3-001"),
            Decision.REJECT,
            0,
            "P6_E3_PATH_POLICY",
        )
    )


def test_e3_a02_outside_allowed_scope(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E3-A02",
            Actor.AGENT,
            Operation.WRITE,
            _path("README.md"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P6_E3_PATH_POLICY",
        )
    )


def test_e3_a03_traversal(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E3-A03",
            Actor.AGENT,
            Operation.WRITE,
            _path(".agents/../src/jamp/run.py"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P3_TARGET_STRUCTURE",
        )
    )


def test_e3_a04_absolute_path(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E3-A04",
            Actor.AGENT,
            Operation.WRITE,
            _path("/tmp/x.py"),
            task,
            evidence(),
            Decision.REJECT,
            0,
            "P3_TARGET_STRUCTURE",
        )
    )


def test_e3_a05_allowed_path_without_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E3-A05",
            Actor.AGENT,
            Operation.WRITE,
            _path(".agents/runner/example.py"),
            task,
            None,
            Decision.INCONCLUSIVE,
            0,
            "P7_EVIDENCE",
        )
    )


def test_e3_p01_allowed_path_with_evidence(task: TaskContract) -> None:
    _assert_case(
        Case(
            "E3-P01",
            Actor.AGENT,
            Operation.WRITE,
            _path(".agents/runner/example.py"),
            task,
            evidence(),
            Decision.ALLOW,
            1,
            "P9_ALLOW",
        )
    )
