"""Canonical, model-facing resume payload builder."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .evidence import Evidence, require_evidence


def build_resume_payload(*, state: str, evidence: Evidence | None, previous_action: str | None = None) -> dict[str, Any]:
    verified = require_evidence(evidence)
    return {
        "state": state,
        "task_id": verified.task_id,
        "source_sha": verified.source_sha,
        "run_ids": list(verified.run_ids),
        "artifact_ids": list(verified.artifact_ids),
        "previous_action": previous_action,
    }
