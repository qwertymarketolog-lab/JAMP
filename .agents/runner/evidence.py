"""Deterministic evidence helpers for Phase A."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    source_sha: str
    task_id: str
    run_ids: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()


def require_evidence(evidence: Evidence | None) -> Evidence:
    if evidence is None or not evidence.source_sha or not evidence.task_id:
        raise ValueError("required evidence is missing")
    return evidence
