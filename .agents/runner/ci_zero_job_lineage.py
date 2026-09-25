"""Fail-closed detector for GitHub Actions zero-job lineage boundaries.

This module is provider-agnostic: GitHub/API adapters supply immutable observations;
the investigator only classifies and links those observations.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class CIObservation:
    sha: str
    workflow: str
    run_id: int | None
    event: str | None
    branch: str | None
    status: str | None
    conclusion: str | None
    jobs_count: int | None


@dataclass(frozen=True)
class Boundary:
    normal_sha: str
    failure_sha: str
    failure_run_id: int
    workflow: str


@dataclass(frozen=True)
class Investigation:
    state: str
    observations: tuple[CIObservation, ...]
    boundary: Boundary | None
    reason: str


def investigate_lineage(
    *,
    start_sha: str,
    workflow: str,
    parent_of: Callable[[str], str | None],
    observe: Callable[[str, str], CIObservation | None],
    max_hops: int = 100,
) -> Investigation:
    """Walk parents until the first normal -> zero-job-failure boundary.

    Missing observations, malformed terminal data, cycles, and exhausted
    search are INCONCLUSIVE. No state is inferred from absent jobs data.
    """

    if not start_sha or not workflow or max_hops < 1:
        return Investigation("INCONCLUSIVE", (), None, "invalid investigation contract")

    seen: set[str] = set()
    observations: list[CIObservation] = []
    current = start_sha

    for _ in range(max_hops):
        if current in seen:
            return Investigation(
                "INCONCLUSIVE", tuple(observations), None, "parent lineage cycle"
            )
        seen.add(current)

        item = observe(current, workflow)
        if item is None:
            return Investigation(
                "INCONCLUSIVE", tuple(observations), None, "missing CI observation"
            )
        if item.sha != current or item.workflow != workflow:
            return Investigation(
                "INCONCLUSIVE", tuple(observations), None, "observation identity mismatch"
            )
        if item.run_id is None or item.status is None or item.conclusion is None:
            return Investigation(
                "INCONCLUSIVE", tuple(observations), None, "incomplete terminal metadata"
            )
        if item.jobs_count is None or item.jobs_count < 0:
            return Investigation(
                "INCONCLUSIVE", tuple(observations), None, "missing or invalid jobs count"
            )

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
                None if len(observations) == 1 else Boundary(
                    normal_sha=observations[-2].sha,
                    failure_sha=item.sha,
                    failure_run_id=observations[-2].run_id,  # type: ignore[arg-type]
                    workflow=workflow,
                ),
                "normal predecessor found"
                if len(observations) > 1
                else "start SHA is not a zero-job failure",
            )

        parent = parent_of(current)
        if not parent:
            return Investigation(
                "INCONCLUSIVE",
                tuple(observations),
                None,
                "zero-job failure has no parent evidence",
            )
        current = parent

    return Investigation(
        "INCONCLUSIVE", tuple(observations), None, "maximum lineage depth reached"
    )
