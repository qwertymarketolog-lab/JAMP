"""Deterministic E1-E3 operation authorization policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from decision import Decision
from evidence import Evidence
from path_policy import evaluate_path
from task_loader import TaskContract


class Actor(StrEnum):
    RUNNER = "runner"
    AGENT = "agent"
    HUMAN = "human"


class Operation(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"
    PUSH = "PUSH"
    MERGE = "MERGE"


class TargetKind(StrEnum):
    PATH = "PATH"
    REF = "REF"


@dataclass(frozen=True)
class Target:
    kind: TargetKind
    value: str


@dataclass(frozen=True)
class Authorization:
    actor: Actor
    operation: Operation
    target: Target
    task_id: str
    source_sha: str


def _validate_actor(actor: Actor | str) -> bool:
    try:
        Actor(actor)
    except (TypeError, ValueError):
        return False
    return True


def _validate_operation(operation: Operation | str) -> bool:
    try:
        Operation(operation)
    except (TypeError, ValueError):
        return False
    return True


def _validate_target_for_operation(operation: Operation, target: Target) -> bool:
    if not isinstance(target, Target):
        return False
    try:
        kind = TargetKind(target.kind)
    except (TypeError, ValueError):
        return False

    expected = {
        Operation.READ: TargetKind.PATH,
        Operation.WRITE: TargetKind.PATH,
        Operation.DELETE: TargetKind.PATH,
        Operation.PUSH: TargetKind.REF,
        Operation.MERGE: TargetKind.REF,
    }[operation]
    return kind is expected and isinstance(target.value, str) and bool(target.value)


def _is_main_ref(value: str) -> bool:
    return value == "main" or value == "refs/heads/main"


def _is_frozen_core_path(value: str) -> bool:
    return value == "src/jamp" or value.startswith("src/jamp/")


def _authorize(
    *,
    actor: Actor | str,
    operation: Operation | str,
    target: Target,
    task: TaskContract,
    evidence: Evidence | None,
) -> tuple[Decision, Authorization | None, str, str]:
    if not _validate_actor(actor):
        return Decision.REJECT, None, "P0_ACTOR", "unknown actor"

    if not _validate_operation(operation):
        return Decision.REJECT, None, "P1_OPERATION", "unknown operation"

    actor_value = Actor(actor)
    operation_value = Operation(operation)

    if not _validate_target_for_operation(operation_value, target):
        return Decision.REJECT, None, "P2_TARGET_KIND", "operation/target mismatch"

    if operation_value in (Operation.READ, Operation.WRITE, Operation.DELETE):
        if target.value.startswith("/") or ".." in target.value.split("/"):
            return Decision.REJECT, None, "P3_TARGET_STRUCTURE", "absolute or traversal path"
    elif target.value.strip() != target.value:
        return Decision.REJECT, None, "P3_TARGET_STRUCTURE", "invalid ref structure"

    if operation_value in (Operation.PUSH, Operation.MERGE) and _is_main_ref(target.value):
        return Decision.REJECT, None, "P4_E1_MAIN_BOUNDARY", "main ref mutation is forbidden"

    if operation_value in (Operation.WRITE, Operation.DELETE) and _is_frozen_core_path(
        target.value
    ):
        return Decision.REJECT, None, "P5_E2_FROZEN_CORE", "Frozen Core mutation is forbidden"

    if operation_value in (Operation.READ, Operation.WRITE, Operation.DELETE):
        if evaluate_path(task, target.value) is Decision.REJECT:
            return Decision.REJECT, None, "P6_E3_PATH_POLICY", "path policy rejected target"

    if evidence is None or not evidence.source_sha or not evidence.task_id:
        return Decision.INCONCLUSIVE, None, "P7_EVIDENCE", "required evidence is missing"

    authorization = Authorization(
        actor=actor_value,
        operation=operation_value,
        target=target,
        task_id=task.task_id,
        source_sha=evidence.source_sha,
    )
    return Decision.ALLOW, authorization, "P9_ALLOW", "operation authorized"


def authorize_operation(
    *,
    actor: Actor | str,
    operation: Operation | str,
    target: Target,
    task: TaskContract,
    evidence: Evidence | None,
) -> tuple[Decision, Authorization | None]:
    decision, authorization, _, _ = _authorize(
        actor=actor,
        operation=operation,
        target=target,
        task=task,
        evidence=evidence,
    )
    return decision, authorization


def evaluate_operation(
    *,
    actor: Actor | str,
    operation: Operation | str,
    target: Target,
    task: TaskContract,
    evidence: Evidence | None,
) -> Decision:
    decision, _ = authorize_operation(
        actor=actor,
        operation=operation,
        target=target,
        task=task,
        evidence=evidence,
    )
    return decision


__all__ = [
    "Actor",
    "Authorization",
    "Operation",
    "Target",
    "TargetKind",
    "authorize_operation",
    "evaluate_operation",
]
