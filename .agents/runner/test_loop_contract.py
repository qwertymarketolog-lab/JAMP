from loop_contract import LoopState, transition


def test_open_to_running_requires_evidence():
    result = transition(LoopState.OPEN, LoopState.RUNNING, evidence=("task loaded",))
    assert result.current is LoopState.RUNNING


def test_running_to_verified_is_forbidden():
    try:
        transition(LoopState.RUNNING, LoopState.VERIFIED, evidence=("bad",))
    except ValueError:
        pass
    else:
        raise AssertionError("RUNNING -> VERIFIED must be fail-closed")


def test_empty_evidence_is_forbidden():
    try:
        transition(LoopState.OPEN, LoopState.RUNNING, evidence=())
    except ValueError:
        pass
    else:
        raise AssertionError("state transition without evidence must fail")
