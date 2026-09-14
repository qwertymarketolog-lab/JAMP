from jamp.research.o4_bounds import BoundState, Interval, propagate_bounds, _tighten
from jamp.research.p0_canonical import Constant, Relation, Variable


def test_o4_equal_symbolic_endpoints_derive_singleton():
    x = Variable("x")
    a = Constant("a")
    constraints = [Relation(">=", x, a), Relation("<=", x, a)]
    bounds = [("o4-input-0", ">=", a), ("o4-input-1", "<=", a)]

    tighten_result = _tighten(x, bounds)
    assert tighten_result.contradiction is False
    assert tighten_result.interval == Interval(x, a, True, a, True)
    assert tighten_result.parents == ("o4-input-0", "o4-input-1")

    propagation_result = propagate_bounds(BoundState(), constraints)
    assert propagation_result.contradiction is False
    assert propagation_result.derived[0].statement_id == "o4-derived-0"
    assert propagation_result.derived[0].expression == Interval(x, a, True, a, True)
    assert propagation_result.derived[0].parents == ("o4-input-0", "o4-input-1")


def test_o4_contradiction_strict_gt_vs_nonstrict_le():
    x = Variable("x")
    a = Constant("a")
    constraints = [Relation(">", x, a), Relation("<=", x, a)]
    bounds = [("o4-input-0", ">", a), ("o4-input-1", "<=", a)]

    tighten_result = _tighten(x, bounds)
    assert tighten_result.contradiction is True
    assert tighten_result.interval is None
    assert tighten_result.parents == ()

    propagation_result = propagate_bounds(BoundState(), constraints)
    assert propagation_result.contradiction is True
    assert propagation_result.derived == ()


def test_o4_contradiction_nonstrict_ge_vs_strict_lt():
    x = Variable("x")
    a = Constant("a")
    constraints = [Relation(">=", x, a), Relation("<", x, a)]
    bounds = [("o4-input-0", ">=", a), ("o4-input-1", "<", a)]

    tighten_result = _tighten(x, bounds)
    assert tighten_result.contradiction is True
    assert tighten_result.interval is None
    assert tighten_result.parents == ()

    propagation_result = propagate_bounds(BoundState(), constraints)
    assert propagation_result.contradiction is True
    assert propagation_result.derived == ()


def test_o4_contradiction_strict_gt_vs_strict_lt():
    x = Variable("x")
    a = Constant("a")
    constraints = [Relation(">", x, a), Relation("<", x, a)]
    bounds = [("o4-input-0", ">", a), ("o4-input-1", "<", a)]

    tighten_result = _tighten(x, bounds)
    assert tighten_result.contradiction is True
    assert tighten_result.interval is None
    assert tighten_result.parents == ()

    propagation_result = propagate_bounds(BoundState(), constraints)
    assert propagation_result.contradiction is True
    assert propagation_result.derived == ()


def test_o4_no_interval_lower_only():
    """x >= a alone: no upper bound -> no interval."""
    x = Variable("x")
    a = Constant("a")
    constraints = [Relation(">=", x, a)]
    bounds = [("o4-input-0", ">=", a)]

    tighten_result = _tighten(x, bounds)
    assert tighten_result.contradiction is False
    assert tighten_result.interval is None
    assert tighten_result.parents == ()

    propagation_result = propagate_bounds(BoundState(), constraints)
    assert propagation_result.contradiction is False
    assert propagation_result.derived == ()


def test_o4_no_interval_distinct_endpoints():
    """x >= a and x <= b with a != b: v0.1 detects only singleton endpoints."""
    x = Variable("x")
    a = Constant("a")
    b = Constant("b")
    constraints = [Relation(">=", x, a), Relation("<=", x, b)]
    bounds = [("o4-input-0", ">=", a), ("o4-input-1", "<=", b)]

    tighten_result = _tighten(x, bounds)
    assert tighten_result.contradiction is False
    assert tighten_result.interval is None
    assert tighten_result.parents == ()

    propagation_result = propagate_bounds(BoundState(), constraints)
    assert propagation_result.contradiction is False
    assert propagation_result.derived == ()


def test_o4_no_interval_empty_bounds():
    """Empty bounds: neither lower nor upper present."""
    x = Variable("x")
    bounds = []
    constraints = []

    tighten_result = _tighten(x, bounds)
    assert tighten_result.contradiction is False
    assert tighten_result.interval is None
    assert tighten_result.parents == ()

    propagation_result = propagate_bounds(BoundState(), constraints)
    assert propagation_result.contradiction is False
    assert propagation_result.derived == ()


if __name__ == "__main__":
    test_o4_equal_symbolic_endpoints_derive_singleton()
    test_o4_contradiction_strict_gt_vs_nonstrict_le()
    test_o4_contradiction_nonstrict_ge_vs_strict_lt()
    test_o4_contradiction_strict_gt_vs_strict_lt()
    test_o4_no_interval_lower_only()
    test_o4_no_interval_distinct_endpoints()
    test_o4_no_interval_empty_bounds()
    print("o4 no-interval tests: PASS")
