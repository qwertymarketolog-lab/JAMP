"""Task loading and path-policy validation for Phase A."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Any

import yaml


class TaskValidationError(ValueError):
    """Raised when a task contract is malformed or unsafe."""


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    version: int
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]


def load_task(text: str) -> TaskContract:
    try:
        data: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TaskValidationError("malformed task YAML") from exc

    if not isinstance(data, dict):
        raise TaskValidationError("task must be a mapping")

    task_id = data.get("task_id")
    version = data.get("version")
    scope = data.get("scope")

    if not isinstance(task_id, str) or not re.fullmatch(r"TASK-[0-9]{3,}", task_id):
        raise TaskValidationError("invalid task_id")
    if not isinstance(version, int) or version < 1:
        raise TaskValidationError("invalid version")
    if not isinstance(scope, dict):
        raise TaskValidationError("missing scope")

    allowed = scope.get("allowed_paths")
    forbidden = scope.get("forbidden_paths")
    if not isinstance(allowed, list) or not all(isinstance(x, str) for x in allowed):
        raise TaskValidationError("invalid allowed_paths")
    if not isinstance(forbidden, list) or not all(isinstance(x, str) for x in forbidden):
        raise TaskValidationError("invalid forbidden_paths")

    return TaskContract(task_id, version, tuple(allowed), tuple(forbidden))


def path_allowed(task: TaskContract, path: str) -> bool:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return False

    def matches(pattern: str) -> bool:
        return candidate.match(pattern) or PurePosixPath(pattern.rstrip("/**")).match(str(candidate))

    if any(matches(pattern) for pattern in task.forbidden_paths):
        return False
    return any(matches(pattern) for pattern in task.allowed_paths)
