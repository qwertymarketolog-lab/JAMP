"""Authoritative deterministic path policy for Phase A."""

from __future__ import annotations

from pathlib import PurePosixPath

from decision import Decision
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
        if pattern.endswith("/**"):
            base = PurePosixPath(pattern.removesuffix("/**"))
            return candidate == base or candidate.is_relative_to(base)
        return candidate.match(pattern)

    # Forbidden scope always takes precedence over allowed scope.
    if any(matches(pattern) for pattern in task.forbidden_paths):
        return Decision.REJECT

    if not any(matches(pattern) for pattern in task.allowed_paths):
        return Decision.REJECT

    return Decision.ALLOW
