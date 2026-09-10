from jamp.research.p11_eventbus import (
    Div,
    Number,
    RootAnchor,
    Var,
    check_rational_branch,
    op_coprime_collision,
    run_p11,
)


def test_expr_structural_equality_and_hashing() -> None:
    assert Number(2) == Number(2)
    assert Var("p") == Var("p")
    assert len({Number(2), Number(2), Var("p"), Var("p")}) == 2


def test_native_collision_positive() -> None:
    state = {
        __import__("jamp.research.p11_eventbus", fromlist=["Equals"]).Equals(
            __import__("jamp.research.p11_eventbus", fromlist=["GCD"]).GCD(
                Var("p"), Var("q")
            ),
            Number(1),
        ),
        Div(Number(2), Var("p")),
        Div(Number(2), Var("q")),
    }
    result = op_coprime_collision(state)
    assert result is not None
    assert Number(2) in result.common_divisors


def test_native_collision_negative() -> None:
    from jamp.research.p11_eventbus import Equals, GCD

    state = {
        Equals(GCD(Var("p"), Var("q")), Number(1)),
        Div(Number(2), Var("p")),
    }
    assert op_coprime_collision(state) is None


def test_p11_c_rational_negative_control() -> None:
    result = run_p11(64, 6)
    assert check_rational_branch(64, 6)
    assert result["branch"] == "RATIONAL_BRANCH"
    assert result["div_q_count"] == 0
    assert result["contradiction"] is None
    assert not any(isinstance(atom, Div) for atom in result["state"])


def test_p11_a_and_b_are_rule_driven() -> None:
    for root, degree in ((32, 4), (128, 6)):
        result = run_p11(root, degree)
        assert result["branch"] == "IRRATIONAL_PIPELINE"
        assert result["div_q_count"] == 1
        assert result["contradiction"] is not None
        assert RootAnchor(root, degree) in result["state"]
        assert Div(Number(2), Var("p")) in result["state"]
        assert Div(Number(2), Var("q")) in result["state"]


def test_p11_runner_contains_no_manual_div_injection() -> None:
    import inspect

    from jamp.research import p11_eventbus

    source = inspect.getsource(p11_eventbus.run_p11)
    assert "state.add(Div(" not in source
    assert "state.add(Div" not in source
