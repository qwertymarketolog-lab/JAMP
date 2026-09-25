"""Deterministic Research Loop v0 ALLOW gate."""

from __future__ import annotations

from decision import Decision
from path_policy import evaluate_path
from task_loader import TaskContract

from provenance import (
    LOCKED_CORE_BLOB,
    ProvenanceEvidence,
    validate_provenance,
)

REQUIRED_CI_FIELDS = {"workflow", "run_id", "job_id", "status", "conclusion"}


def evaluate_gate(
    *,
    task: TaskContract,
    evidence: ProvenanceEvidence,
    expected_source_sha: str,
    expected_target_sha: str,
    required_workflows: tuple[str, ...],
) -> Decision:
    """Allow only on complete, non-contradictory, policy-compliant evidence."""

    if not validate_provenance(evidence):
        return Decision.INCONCLUSIVE

    if evidence.source_sha != expected_source_sha:
        return Decision.INCONCLUSIVE
    if evidence.target_sha != expected_target_sha:
        return Decision.INCONCLUSIVE
    if task.base_ref and evidence.base_ref != task.base_ref:
        return Decision.INCONCLUSIVE
    if evidence.frozen_core_blob != LOCKED_CORE_BLOB:
        return Decision.REJECT

    path_decisions = [evaluate_path(task, path) for path in evidence.changed_paths]
    if any(decision is Decision.REJECT for decision in path_decisions):
        return Decision.REJECT
    if not evidence.changed_paths or any(
        decision is not Decision.ALLOW for decision in path_decisions
    ):
        return Decision.INCONCLUSIVE

    if not required_workflows:
        return Decision.INCONCLUSIVE

    by_workflow: dict[str, list] = {}
    for check in evidence.ci_checks:
        if not all(getattr(check, field) for field in REQUIRED_CI_FIELDS):
            return Decision.INCONCLUSIVE
        by_workflow.setdefault(check.workflow, []).append(check)

    for workflow in required_workflows:
        checks = by_workflow.get(workflow, [])
        if len(checks) != 1:
            return Decision.INCONCLUSIVE
        check = checks[0]
        if check.status != "completed" or check.conclusion != "success":
            return Decision.REJECT

    if set(by_workflow) - set(required_workflows):
        return Decision.INCONCLUSIVE

    return Decision.ALLOW
