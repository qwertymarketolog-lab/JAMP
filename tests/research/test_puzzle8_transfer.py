from tests.research.puzzle8_run_adapter import GOAL, run_puzzle8_via_core


def test_puzzle8_transfers_through_existing_core():
    result = run_puzzle8_via_core()
    assert result.state == GOAL
    assert result.steps == 2
    assert result.iterations == 2
    assert result.stop_reason.kind == "terminal"
