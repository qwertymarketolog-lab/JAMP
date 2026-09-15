from jamp.run import Run, RunResult, StopReason, run


def test_run_terminal():
    class Counter:
        budget = 10
        def initial(self): return 0
        def candidates(self, s): return [s + 1]
        def admissible(self, s, c): return True
        def apply(self, s, c): return c
        def terminal(self, s): return s >= 2
        def strategy(self, s, cands): return next(iter(cands))

    result = run(Counter())
    assert result.state == 2
    assert result.steps == 2
    assert result.iterations == 2
    assert result.stop_reason.kind == "terminal"


def test_run_budget():
    class Endless:
        budget = 5
        def initial(self): return 0
        def candidates(self, s): return [s + 1]
        def admissible(self, s, c): return True
        def apply(self, s, c): return c
        def terminal(self, s): return False
        def strategy(self, s, cands): return next(iter(cands))

    result = run(Endless())
    assert result.state == 5
    assert result.steps == 5
    assert result.iterations == 5
    assert result.stop_reason.kind == "budget"


def test_run_exhausted():
    class Nothing:
        budget = 5
        def initial(self): return 0
        def candidates(self, s): return []
        def admissible(self, s, c): return True
        def apply(self, s, c): return c
        def terminal(self, s): return False
        def strategy(self, s, cands): return next(iter(cands))

    result = run(Nothing())
    assert result.state == 0
    assert result.steps == 0
    assert result.iterations == 1
    # iterations counts entered turns, not exit turns.
    assert result.stop_reason.kind == "exhausted"


def test_run_error():
    class Boom:
        budget = 5
        def initial(self): return 0
        def candidates(self, s): return [1]
        def admissible(self, s, c): return True
        def apply(self, s, c): raise ValueError("boom")
        def terminal(self, s): return False
        def strategy(self, s, cands): return next(iter(cands))

    result = run(Boom())
    assert result.steps == 0
    assert result.iterations == 1
    # iterations counts entered turns, not exit turns.
    assert result.stop_reason.kind == "error"
    assert "boom" in result.stop_reason.detail


if __name__ == "__main__":
    test_run_terminal()
    test_run_budget()
    test_run_exhausted()
    test_run_error()
    print("run contract tests: PASS")


def test_run_on_empty_recovers():
    class R:
        budget = 10
        def initial(self): return 0
        def candidates(self, s): return [] if s < 2 else [s]
        def admissible(self, s, c): return True
        def apply(self, s, c): return c
        def terminal(self, s): return s >= 2
        def strategy(self, s, cands): return next(iter(cands))
        def on_empty(self, s): return s + 1
    result = run(R())
    assert result.state == 2
    assert result.steps == 0
    assert result.iterations == 2
    # iterations counts entered turns, not exit turns.
    assert result.stop_reason.kind == "terminal"


def test_run_on_empty_returns_none():
    class R:
        budget = 10
        def initial(self): return 0
        def candidates(self, s): return []
        def admissible(self, s, c): return True
        def apply(self, s, c): return c
        def terminal(self, s): return False
        def strategy(self, s, cands): return next(iter(cands))
        def on_empty(self, s): return None
    result = run(R())
    assert result.state == 0
    assert result.steps == 0
    assert result.iterations == 1
    # iterations counts entered turns, not exit turns.
    assert result.stop_reason.kind == "exhausted"


def test_run_on_empty_budget():
    class R:
        budget = 5
        def initial(self): return 0
        def candidates(self, s): return []
        def admissible(self, s, c): return True
        def apply(self, s, c): return c
        def terminal(self, s): return False
        def strategy(self, s, cands): return next(iter(cands))
        def on_empty(self, s): return s + 1
    result = run(R())
    assert result.state == 5
    assert result.steps == 0
    assert result.iterations == 5
    # iterations counts entered turns, not exit turns.
    assert result.stop_reason.kind == "budget"
