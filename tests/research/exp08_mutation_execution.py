from __future__ import annotations

from dataclasses import asdict
from typing import Any

from tests.research.exp07_replay import ReplayEvent, replay
from tests.research.exp08_mutation_harness import MUTATION_IDS, baseline_events, mutate


def _serialize_event(event: ReplayEvent) -> dict[str, Any]:
    """Serialize a ReplayEvent without changing its semantics."""
    return asdict(event)


def _raw_observation(
    mutation_id: str,
    mutated_events: tuple[ReplayEvent, ...],
) -> dict[str, Any]:
    """Execute replay once and capture input provenance and raw observations."""
    serialized_input = [_serialize_event(event) for event in mutated_events]

    try:
        result = replay(mutated_events)
        return {
            "mutation_id": mutation_id,
            "input_events": serialized_input,
            "replay_succeeded": True,
            "exception_type": None,
            "exception_message": None,
            "canonical_events": [
                _serialize_event(event) for event in result.canonical_events
            ],
            "dag_hash": result.dag_hash,
            "merged_result": result.merged_result,
        }
    except Exception as exc:
        return {
            "mutation_id": mutation_id,
            "input_events": serialized_input,
            "replay_succeeded": False,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "canonical_events": None,
            "dag_hash": None,
            "merged_result": None,
        }


def collect_raw_observations() -> list[dict[str, Any]]:
    """Execute all frozen EXP-08 mutations without A/B/C/D classification."""
    observations: list[dict[str, Any]] = []
    for mutation_id in MUTATION_IDS:
        baseline = baseline_events()
        mutated_events = mutate(baseline, mutation_id)
        observations.append(_raw_observation(mutation_id, mutated_events))
    return observations
