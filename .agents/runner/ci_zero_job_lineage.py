"""Investigate GitHub Actions zero-job workflow lineage.

This module deliberately fails closed when the authoritative workflow lineage
cannot be established.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


@dataclass(frozen=True)
class CIObservation:
    run_id: int
    status: str
    conclusion: str | None
    jobs_count: int
    parent_run_id: int | None


@dataclass(frozen=True)
class Investigation:
    state: str
    observations: tuple[CIObservation, ...]
    root_run_id: int | None
    reason: str


Observer = Callable[[int], CIObservation]


def investigate_lineage(
    run_id: int,
    observe: Observer,
    workflow: str,
    max_hops: int = 8,
) -> Investigation:
    """Trace a zero-job failure through authoritative parent workflow runs."""
    del workflow
    current = run_id
    seen: set[int] = set()
    observations: list[CIObservation] = []

    for _ in range(max_hops):
        if current in seen:
            return Investigation("INCONCLUSIVE", tuple(observations), None, "parent lineage cycle")
        seen.add(current)

        item = observe(current, workflow)
        observations.append(item)

        zero_job_failure = (
            item.status == "completed"
            and item.conclusion == "failure"
            and item.jobs_count == 0
        )
        if not zero_job_failure:
            return Investigation(
                "VERIFIED" if len(observations) > 1 else "INCONCLUSIVE",
                tuple(observations),
                current,
                "terminal non-zero-job workflow state",
            )

        parent = item.parent_run_id
        if parent is None:
            return Investigation(
                "INCONCLUSIVE",
                tuple(observations),
                None,
                "zero-job failure has no authoritative parent",
            )
        current = parent

    return Investigation("INCONCLUSIVE", tuple(observations), None, "maximum lineage depth reached")
