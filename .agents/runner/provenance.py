"""Minimal immutable provenance contract for Research Loop v0."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

LOCKED_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"


class IndependenceClass(StrEnum):
    UNVERIFIED_LOCAL = "unverified_local"
    VERIFIED_INDEPENDENT_RUNNER = "verified_independent_runner"


@dataclass(frozen=True)
class CICheck:
    workflow: str
    run_id: str
    job_id: str
    status: str
    conclusion: str


@dataclass(frozen=True)
class ProvenanceEvidence:
    task_id: str
    source_sha: str
    target_sha: str
    base_ref: str
    branch: str
    pr_number: int
    changed_paths: tuple[str, ...]
    ci_checks: tuple[CICheck, ...]
    frozen_core_blob: str


def derive_independence(evidence: ProvenanceEvidence) -> IndependenceClass:
    """Classify evidence conservatively without trusting agent-supplied fields."""
    del evidence
    return IndependenceClass.UNVERIFIED_LOCAL


def validate_provenance(evidence: ProvenanceEvidence) -> bool:
    return bool(
        evidence.task_id
        and evidence.source_sha
        and evidence.target_sha
        and evidence.base_ref
        and evidence.branch
        and evidence.pr_number > 0
        and evidence.ci_checks
        and evidence.frozen_core_blob
    )
