"""Authoritative deterministic path policy for Phase A."""

from __future__ import annotations

from pathlib import PurePosixPath

from policy import Decision
from task_loader import TaskContract


def evaluate_path(task: TaskContract, candidate_path: str) -> Decision:
    """Return the authoritative permission for a candidate repository path."""
    try:
        candidate = PurePosixPath(candidate_path)
    except (TypeError, ValueError):
        return Decision.REJECT

    if candidate.is_absolute() or ".." in candidate.parts:
        return Decision.REJECT

    def matches(pattern: str) -> bool:
        normalized = pattern.removesuffix("/**")
        return candidate.match(pattern) or candidate.match(normalized)

    # Forbidden scope always takes precedence over allowed scope.
    if any(matches(pattern) for pattern in task.forbidden_paths):
        return Decision.REJECT

    if not any(matches(pattern) for pattern in task.allowed_paths):
        return Decision.REJECT

    return Decision.ALLOW
