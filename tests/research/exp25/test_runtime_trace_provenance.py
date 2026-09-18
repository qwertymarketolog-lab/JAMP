"""Research vectors for EXP-25 runtime trace provenance."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tests.research.exp25.runtime_trace_provenance import (
    build_runtime_trace_observation,
    payload_digest,
)

BASE_RECORD = {
    "exp24_parent_ref": "exp24:boundary-001",
    "exp23_parent_ref": "exp23:observation-001",
    "events": [
        {
            "step_index": 0,
            "event_kind": "fixture_input",
            "payload_digest": payload_digest({"value": "alpha"}),
        },
        {
            "step_index": 1,
            "event_kind": "fixture_output",
            "payload_digest": payload_digest({"value": "beta"}),
        },
    ],
}


def test_missing_parent_envelope_reference_is_rejected() -> None:
    changed = deepcopy(BASE_RECORD)
    changed["exp24_parent_ref"] = ""
    with pytest.raises(ValueError, match="parent references"):
        build_runtime_trace_observation(changed)


def test_missing_exp23_lineage_reference_is_rejected() -> None:
    changed = deepcopy(BASE_RECORD)
    changed["exp23_parent_ref"] = ""
    with pytest.raises(ValueError, match="parent references"):
        build_runtime_trace_observation(changed)


def test_step_reordering_changes_trace_identity() -> None:
    baseline = build_runtime_trace_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["events"].reverse()
    changed["events"][0]["step_index"] = 0
    changed["events"][1]["step_index"] = 1
    reordered = build_runtime_trace_observation(changed)
    assert reordered.cumulative_digest != baseline.cumulative_digest


def test_identical_fixture_stream_is_deterministic() -> None:
    first = build_runtime_trace_observation(BASE_RECORD)
    repeated = build_runtime_trace_observation(deepcopy(BASE_RECORD))
    assert repeated == first
    assert repeated.trace_id == first.trace_id


def test_semantic_verdict_keys_are_not_trace_fields() -> None:
    observation = build_runtime_trace_observation(BASE_RECORD)
    serialized = {
        "schema_version": observation.schema_version,
        "exp24_parent_ref": observation.exp24_parent_ref,
        "exp23_parent_ref": observation.exp23_parent_ref,
        "events": [
            {
                "step_index": event.step_index,
                "event_kind": event.event_kind,
                "payload_digest": event.payload_digest,
            }
            for event in observation.events
        ],
        "cumulative_digest": observation.cumulative_digest,
    }
    assert (
        not {
            "goal_met",
            "error_bad",
            "policy_violated",
        }
        & serialized.keys()
    )


def test_runtime_and_core_isolation() -> None:
    import inspect

    from tests.research.exp25 import runtime_trace_provenance

    source = inspect.getsource(runtime_trace_provenance)
    assert "src/jamp" not in source
    assert "import socket" not in source
    assert "import requests" not in source
