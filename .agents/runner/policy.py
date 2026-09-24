"""Fail-closed Policy Gate for Phase A."""

from __future__ import annotations

from decision import Decision
from path_policy import evaluate_path
from task_loader import TaskContract


def evaluate(
    *,
    task: TaskContract,
    candidate_path: str,
    required_evidence_present: bool,
) -> Decision:
    path_decision = evaluate_path(task, candidate_path)
    if path_decision is Decision.REJECT:
        return Decision.REJECT
    if not required_evidence_present:
        return Decision.INCONCLUSIVE
    return Decision.ALLOW
