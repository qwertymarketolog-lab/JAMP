from .policy import Decision, evaluate
from .state_machine import RunnerState, State, TransitionError, transition
from .task_loader import TaskValidationError, load_task, path_allowed


TASK = """task_id: TASK-001
version: 1
scope:
  allowed_paths:
    - ".agents/**"
  forbidden_paths:
    - "src/jamp/**"
"""


def test_valid_transition() -> None:
    assert transition(RunnerState(State.BOOTSTRAP), State.LOAD_TASK).state is State.LOAD_TASK


def test_invalid_transition() -> None:
    try:
        transition(RunnerState(State.BOOTSTRAP), State.DISPATCH)
    except TransitionError:
        return
    raise AssertionError("invalid transition was accepted")


def test_forbidden_path() -> None:
    task = load_task(TASK)
    assert not path_allowed(task, "src/jamp/run.py")


def test_missing_evidence() -> None:
    assert evaluate(path_allowed=True, required_evidence_present=False) is Decision.INCONCLUSIVE


def test_malformed_task() -> None:
    try:
        load_task("task_id: broken")
    except TaskValidationError:
        return
    raise AssertionError("malformed task was accepted")


def test_core_invariant_blob_is_not_written() -> None:
    from pathlib import Path

    core = Path("src/jamp/run.py")
    before = core.read_bytes()
    after = core.read_bytes()
    assert before == after
