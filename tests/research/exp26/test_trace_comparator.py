"""Research vectors for EXP-26 multi-agent trace comparison."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tests.research.exp26.trace_comparator import (
    TraceStep,
    TraceStream,
    compare_traces,
    payload_digest,
)


def _stream(agent_id: str = "agent-a") -> TraceStream:
    return TraceStream(
        agent_id=agent_id,
        exp24_parent_ref="exp24:boundary-001",
        exp23_parent_ref="exp23:observation-001",
        steps=(
            TraceStep(
                step_index=0,
                event_kind="fixture_input",
                payload_digest=payload_digest({"value": "alpha"}),
            ),
            TraceStep(
                step_index=1,
                event_kind="fixture_output",
                payload_digest=payload_digest({"value": "beta"}),
            ),
        ),
    )


def test_identical_stream_parity_is_empty() -> None:
    left = _stream("agent-a")
    right = deepcopy(left)

    comparison = compare_traces(left, right)

    assert comparison.identical is True
    assert comparison.differences == ()


def test_payload_divergence_reports_first_structural_index() -> None:
    left = _stream("agent-a")
    changed = list(left.steps)
    changed[1] = TraceStep(
        step_index=1,
        event_kind="fixture_output",
        payload_digest=payload_digest({"value": "gamma"}),
    )
    right = TraceStream(
        agent_id="agent-b",
        exp24_parent_ref=left.exp24_parent_ref,
        exp23_parent_ref=left.exp23_parent_ref,
        steps=tuple(changed),
    )

    comparison = compare_traces(left, right)

    assert comparison.identical is False
    assert comparison.differences[0].step_index == 1
    assert comparison.differences[0].reason == "payload_digest"


def test_sequence_reordering_is_detected() -> None:
    left = _stream("agent-a")
    right_steps = (
        TraceStep(
            step_index=0,
            event_kind=left.steps[1].event_kind,
            payload_digest=left.steps[1].payload_digest,
        ),
        TraceStep(
            step_index=1,
            event_kind=left.steps[0].event_kind,
            payload_digest=left.steps[0].payload_digest,
        ),
    )
    right = TraceStream(
        agent_id="agent-b",
        exp24_parent_ref=left.exp24_parent_ref,
        exp23_parent_ref=left.exp23_parent_ref,
        steps=right_steps,
    )

    comparison = compare_traces(left, right)

    assert comparison.identical is False
    assert comparison.differences[0].step_index == 0


def test_lineage_mismatch_rejects_comparison() -> None:
    left = _stream("agent-a")
    right = TraceStream(
        agent_id="agent-b",
        exp24_parent_ref="exp24:boundary-002",
        exp23_parent_ref=left.exp23_parent_ref,
        steps=left.steps,
    )

    with pytest.raises(ValueError, match="lineage references must match"):
        compare_traces(left, right)


def test_comparator_is_non_semantic_and_isolated() -> None:
    import inspect

    from tests.research.exp26 import trace_comparator

    source = inspect.getsource(trace_comparator)
    assert "goal_met" not in source
    assert "error_bad" not in source
    assert "policy_violated" not in source
    assert "src/jamp" not in source
    assert "import socket" not in source
    assert "import requests" not in source
