from __future__ import annotations

from collections.abc import Iterable

from research.exp21.observation_source import ObservationSource


def federate_sources(sources: Iterable[ObservationSource]) -> tuple[str, ...]:
    """Return a read-only flattened view of observation ids from all sources."""
    return tuple(observation_id for source in sources for observation_id in source.observation_ids)
