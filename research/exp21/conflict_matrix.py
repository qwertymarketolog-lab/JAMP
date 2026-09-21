from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any


def build_conflict_matrix(observations: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Classify observations sharing a subject/event across independent sources."""
    groups: dict[tuple[Any, Any], list[Mapping[str, Any]]] = defaultdict(list)
    for observation in observations:
        groups[(observation.get("subject"), observation.get("event"))].append(observation)

    matrix: list[dict[str, Any]] = []
    for (subject, event), group in groups.items():
        source_ids = tuple(observation.get("source_id") for observation in group)
        values = {observation.get("value") for observation in group}
        if len(group) < 2:
            classification = "MISSING"
        elif len(values) > 1:
            classification = "CONFLICT"
        else:
            classification = "AGREEMENT"
        matrix.append(
            {
                "subject": subject,
                "event": event,
                "sources": source_ids,
                "classification": classification,
            }
        )
    return matrix
