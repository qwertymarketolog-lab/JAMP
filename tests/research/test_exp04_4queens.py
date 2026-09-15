from __future__ import annotations

from jamp.run import run

from queens_adapter import FourQueensAdapter


def test_exp04a_find_one_mode() -> None:
    result = run(FourQueensAdapter("FIND_ONE"))
    state = result.state
    events = state.events

    assert result.stop_reason.kind == "terminal"
    assert len(state.solutions) == 1
    assert state.solutions[0] == (2, 4, 1, 3)

    kinds = [event.kind for event in events]
    assert "PRUNE" in kinds
    assert "BACKTRACK" in kinds
    assert "TERMINAL_SAT" in kinds

    prune_events = [event for event in events if event.kind == "PRUNE"]
    assert prune_events
    assert all("conflict_with_row" in event.details for event in prune_events)

    sat_events = [event for event in events if event.kind == "TERMINAL_SAT"]
    assert len(sat_events) == 1
    assert sat_events[0].details["solution_vector"] == (2, 4, 1, 3)


def test_exp04b_exhaustive_mode() -> None:
    result = run(FourQueensAdapter("EXHAUSTIVE"))
    state = result.state
    events = state.events

    assert result.stop_reason.kind == "terminal"
    assert len(state.solutions) == 2
    assert state.solutions == ((2, 4, 1, 3), (3, 1, 4, 2))

    backtracks = [event for event in events if event.kind == "BACKTRACK"]
    prunes = [event for event in events if event.kind == "PRUNE"]
    sat_events = [event for event in events if event.kind == "TERMINAL_SAT"]

    assert len(sat_events) == 2
    assert backtracks
    assert prunes
    assert any(event.details["from_row"] >= 3 for event in backtracks)

    # At least one real dead-end is immediately followed by backtracking.
    assert any(
        events[index - 1].kind == "PRUNE" and event.kind == "BACKTRACK"
        for index, event in enumerate(events)
        if index > 0
    )

    # Every recorded event preserves the observed board transition.
    for event in events:
        assert event.board_before is not None
        assert event.board_after is not None

    for event in backtracks:
        assert event.details["from_row"] > event.details["to_row"]
        assert event.board_before != event.board_after
