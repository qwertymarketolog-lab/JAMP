"""P16.2 deterministic causal ordering and vector-clock contracts."""
from __future__ import annotations

import ast
import random

import pytest

from jamp.domain import CausalConsistencyError, EventNode
from jamp.domain.causal import (
    CausalRelation,
    VectorClock,
    compute_vector_clocks,
    sort_causal_order,
)


def make_events() -> list[EventNode]:
    genesis = EventNode("GENESIS", "Genesis", {})
    a = EventNode("A", "A", {"value": 1}, ("GENESIS",))
    b = EventNode("B", "B", {"value": 2}, ("GENESIS",))
    c = EventNode("C", "C", {"value": 3}, ("A", "B"))
    d = EventNode("D", "D", {"value": 4}, ("B",))
    return [genesis, a, b, c, d]


def test_p16_2_sort_is_deterministic_across_input_permutations() -> None:
    events = make_events()
    expected = tuple(event.event_id for event in sort_causal_order(events))

    for seed in range(20):
        shuffled = events[:]
        random.Random(seed).shuffle(shuffled)
        assert tuple(event.event_id for event in sort_causal_order(shuffled)) == expected


def test_p16_2_parents_always_precede_children() -> None:
    ordered = sort_causal_order(make_events())
    positions = {event.event_id: index for index, event in enumerate(ordered)}
    for event in ordered:
        for parent_id in event.parent_ids:
            assert positions[parent_id] < positions[event.event_id]


def test_p16_2_concurrent_tie_break_uses_digest() -> None:
    events = make_events()
    ordered = sort_causal_order(events)
    concurrent = [event for event in events if event.event_id in {"A", "B"}]
    expected = tuple(sorted(concurrent, key=lambda event: event.digest))
    actual = tuple(event for event in ordered if event.event_id in {"A", "B"})
    assert actual == expected


def test_p16_2_vector_clock_semantics() -> None:
    clocks = dict(compute_vector_clocks(make_events()))
    assert clocks["GENESIS"].as_dict() == {"GENESIS": 1}
    assert clocks["A"].as_dict() == {"A": 1, "GENESIS": 1}
    assert clocks["B"].as_dict() == {"B": 1, "GENESIS": 1}
    assert clocks["C"].as_dict() == {"A": 1, "B": 1, "C": 1, "GENESIS": 1}
    assert clocks["D"].as_dict() == {"B": 1, "D": 1, "GENESIS": 1}

    assert clocks["A"].relation(clocks["C"]) is CausalRelation.BEFORE
    assert clocks["C"].relation(clocks["A"]) is CausalRelation.AFTER
    assert clocks["A"].relation(clocks["B"]) is CausalRelation.CONCURRENT
    assert clocks["A"].relation(clocks["A"]) is CausalRelation.EQUAL


def test_p16_2_vector_clock_is_immutable() -> None:
    clock = VectorClock.from_mapping({"A": 1})
    with pytest.raises(Exception):
        clock.components += (("B", 1),)  # type: ignore[misc]


def test_p16_2_missing_parent_is_rejected() -> None:
    event = EventNode("A", "A", {}, ("MISSING",))
    with pytest.raises(CausalConsistencyError, match="missing parent"):
        sort_causal_order([event])


def test_p16_2_cycle_is_rejected() -> None:
    a = EventNode("A", "A", {}, ("B",))
    b = EventNode("B", "B", {}, ("A",))
    with pytest.raises(CausalConsistencyError, match="cycle"):
        sort_causal_order([a, b])


def test_p16_2_duplicate_event_id_is_rejected() -> None:
    a = EventNode("A", "A", {})
    b = EventNode("A", "B", {})
    with pytest.raises(CausalConsistencyError, match="duplicate event_id"):
        sort_causal_order([a, b])


def test_p16_2_ast_isolation() -> None:
    source = open("src/jamp/domain/causal.py", encoding="utf-8").read()
    tree = ast.parse(source)
    forbidden = {"Registry", "CommitManager", "JAMPEngine"}
    imported = {
        alias.name.split(".")[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        alias.name.split(".")[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    )
    assert imported.isdisjoint(forbidden)
