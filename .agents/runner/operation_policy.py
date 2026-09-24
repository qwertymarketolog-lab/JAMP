from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from decision import Decision
from evidence import Evidence
from path_policy import evaluate_path
from task_loader import TaskContract


class Actor(str, Enum):
    RUNNER = "runner"
    AGENT = "agent"
    HUMAN = "human"


class Operation(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"
    PUSH = "PUSH"
    MERGE = "MERGE"


class TargetKind(str, Enum):
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


def _validate_actor(actor: Actor | str) -> Actor | None:
    try:
        return actor if isinstance(actor, Actor) else Actor(actor)
    except ValueError:
        return None


def _validate_operation(operation: Operation | str) -> Operation | None:
    try:
        return operation if isinstance(operation, Operation) else Operation(operation)
    except ValueError:
        return None


def _validate_target_for_operation(
    operation: Operation, target: Target
) -> bool:
    if not isinstance(target, Target) or not isinstance(target.kind, TargetKind):
        return False
    if not isinstance(target.value, str) or not target.value:
        return False
    if operation in (Operation.READ, Operation.WRITE, Operation.DELETE):
        return target.kind is TargetKind.PATH
    return target.kind is TargetKind.REF


def _is_main_ref(value: str) -> bool:
    return value == "main" or value == "refs/heads/main"


def _is_frozen_core_path(value: str) -> bool:
    return value == "src/jamp/run.py" or value.startswith("src/jamp/")


def _authorize(
    *,
    actor: Actor | str,
    operation: Operation | str,
    target: Target,
    task: TaskContract,
    evidence: Evidence | None,
) -> tuple[Decision, Authorization | None, str, str]:
    actor_value = _validate_actor(actor)
    if actor_value is None:
        return Decision.REJECT, None, "P0_ACTOR", "unknown actor"

    operation_value = _validate_operation(operation)
    if operation_value is None:
        return Decision.REJECT, None, "P1_OPERATION", "unknown operation"

    if not _validate_target_for_operation(operation_value, target):
        return Decision.REJECT, None, "P2_TARGET_KIND", "target kind/value mismatch"

    if operation_value in (Operation.PUSH, Operation.MERGE) and _is_main_ref(target.value):
        return Decision.REJECT, None, "P4_E1_MAIN_BOUNDARY", "main ref mutation is forbidden"

    if operation_value in (Operation.WRITE, Operation.DELETE) and _is_frozen_core_path(
        target.value
    ):
        return Decision.REJECT, None, "P5_E2_FROZEN_CORE", "Frozen Core mutation is forbidden"

    if (
        operation_value in (Operation.READ, Operation.WRITE, Operation.DELETE)
        and evaluate_path(task, target.value) is Decision.REJECT
    ):
        return Decision.REJECT, None, "P6_E3_PATH_POLICY", "path policy rejected target"

    if evidence is None or not evidence.source_sha or not evidence.task_id:
        return Decision.INCONCLUSIVE, None, "P7_EVIDENCE", "required evidence is missing"

    authorization = Authorization(
        actor=actor_value,
        operation=operation_value,
        target=target,
        task_id=evidence.task_id,
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
    decision, _, _, _ = _authorize(
        actor=actor,
        operation=operation,
        target=target,
        task=task,
        evidence=evidence,
    )
    return decision
