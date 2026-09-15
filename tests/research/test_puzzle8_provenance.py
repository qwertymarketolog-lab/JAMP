from jamp.run import run
from tests.research.puzzle8_run_adapter import GOAL, START, Puzzle8Adapter


def test_puzzle8_provenance_transfers_without_core_change():
    adapter = Puzzle8Adapter()
    result = run(adapter)
    assert result.state == GOAL
    assert result.steps == 2
    assert result.iterations == 2
    assert result.stop_reason.kind == "terminal"
    assert adapter.history == [
        (START, "RIGHT", (1, 2, 3, 4, 5, 6, 7, 0, 8)),
        ((1, 2, 3, 4, 5, 6, 7, 0, 8), "RIGHT", GOAL),
    ]
