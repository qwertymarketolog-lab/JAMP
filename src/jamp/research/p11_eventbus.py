"""P11 experimental event-bus baseline.

This module isolates the P11 rational-branch guard, root anchor, prime-power
extraction, fixpoint iteration, and native coprime collision listener.

It is intentionally self-contained: it does not modify the established P17+
research engine. The purpose is to provide a falsifiable baseline for replacing
the former simulated Div-atom injection with rule-driven state evolution.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass


class Expr:
    """Base AST node with structural equality and deterministic diagnostics."""

    def __hash__(self) -> int:
        return hash(self._key())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Expr) and self._key() == other._key()

    def __repr__(self) -> str:
        return str(self._key())

    def _key(self) -> tuple[object, ...]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class Number(Expr):
    val: int

    def _key(self) -> tuple[object, ...]:
        return ("num", self.val)


@dataclass(frozen=True, slots=True)
class Var(Expr):
    name: str

    def _key(self) -> tuple[object, ...]:
        return ("var", self.name)


@dataclass(frozen=True, slots=True)
class GCD(Expr):
    a: Expr
    b: Expr

    def _key(self) -> tuple[object, ...]:
        return ("gcd", self.a, self.b)


@dataclass(frozen=True, slots=True)
class Equals(Expr):
    left: Expr
    right: Expr

    def _key(self) -> tuple[object, ...]:
        return ("=", self.left, self.right)


@dataclass(frozen=True, slots=True)
class Div(Expr):
    divisor: Expr
    target: Expr

    def _key(self) -> tuple[object, ...]:
        return ("div", self.divisor, self.target)


@dataclass(frozen=True, slots=True)
class RootAnchor(Expr):
    """Structural anchor for p^n = root * q^n."""

    root: int
    degree: int

    def _key(self) -> tuple[object, ...]:
        return ("root_anchor", self.root, self.degree)


@dataclass(frozen=True, slots=True)
class Contradiction:
    reason: str
    common_divisors: frozenset[Expr]


State = set[Expr]
Rule = Callable[[State, RootAnchor], set[Expr]]


def factorize(num: int) -> dict[int, int]:
    if num < 1:
        raise ValueError("factorize() requires a positive integer")
    factors: dict[int, int] = {}
    divisor = 2
    remaining = num
    while divisor * divisor <= remaining:
        while remaining % divisor == 0:
            factors[divisor] = factors.get(divisor, 0) + 1
            remaining //= divisor
        divisor += 1
    if remaining > 1:
        factors[remaining] = factors.get(remaining, 0) + 1
    return factors


def check_rational_branch(root: int, degree: int) -> bool:
    """Return True iff root is a perfect degree-th power."""

    if degree <= 0:
        raise ValueError("degree must be positive")
    factors = factorize(root)
    return bool(factors) and all(exp % degree == 0 for exp in factors.values())


def rule_root_anchor(state: State, anchor: RootAnchor) -> set[Expr]:
    """Emit the anchor once it is part of the active state."""

    return {anchor} if anchor in state else set()


def rule_prime_power_extraction(state: State, anchor: RootAnchor) -> set[Expr]:
    """React to a real RootAnchor and derive prime divisibility facts."""

    if anchor not in state:
        return set()

    atoms: set[Expr] = set()
    for prime in factorize(anchor.root):
        atoms.add(Div(Number(prime), Var("p")))
        atoms.add(Div(Number(prime), Var("q")))
    return atoms


def op_coprime_collision(state: State) -> Contradiction | None:
    """Detect common divisors under the active gcd(p, q) = 1 constraint."""

    divs_p = {
        atom.divisor
        for atom in state
        if isinstance(atom, Div) and atom.target == Var("p")
    }
    divs_q = {
        atom.divisor
        for atom in state
        if isinstance(atom, Div) and atom.target == Var("q")
    }

    coprime_fact = Equals(GCD(Var("p"), Var("q")), Number(1))
    if coprime_fact not in state:
        return None

    common = frozenset(divs_p.intersection(divs_q))
    if not common:
        return None

    return Contradiction(
        reason="Prime divisor is present for both p and q under gcd(p,q)=1",
        common_divisors=common,
    )


def run_fixpoint(
    state: State,
    anchor: RootAnchor,
    rules: Iterable[Rule],
    max_rounds: int = 32,
) -> tuple[State, Contradiction | None, int]:
    """Run registered rules until a fixpoint or native collision is reached."""

    if max_rounds <= 0:
        raise ValueError("max_rounds must be positive")

    active = set(state)
    for round_number in range(1, max_rounds + 1):
        collision = op_coprime_collision(active)
        if collision is not None:
            return active, collision, round_number

        additions: set[Expr] = set()
        for rule in rules:
            additions.update(rule(active, anchor))
        additions.difference_update(active)

        if not additions:
            return active, None, round_number
        active.update(additions)

    raise RuntimeError("P11 event bus did not reach a fixpoint within max_rounds")


def run_p11(root: int, degree: int) -> dict[str, object]:
    """Execute one P11 case without direct Div injection in the runner."""

    initial: State = {
        Equals(GCD(Var("p"), Var("q")), Number(1)),
    }

    if check_rational_branch(root, degree):
        return {
            "branch": "RATIONAL_BRANCH",
            "state": initial,
            "div_q_count": 0,
            "contradiction": None,
            "rounds": 0,
        }

    anchor = RootAnchor(root, degree)
    initial.add(anchor)
    final_state, contradiction, rounds = run_fixpoint(
        initial,
        anchor,
        rules=(rule_root_anchor, rule_prime_power_extraction),
    )
    div_q_count = sum(
        isinstance(atom, Div) and atom.target == Var("q") for atom in final_state
    )
    return {
        "branch": "IRRATIONAL_PIPELINE",
        "state": final_state,
        "div_q_count": div_q_count,
        "contradiction": contradiction,
        "rounds": rounds,
    }


P11_CASES = (
    (64, 6, "P11-C (⁶√64 - Negative Control)"),
    (32, 4, "P11-A (⁴√32)"),
    (128, 6, "P11-B (⁶√128)"),
)


if __name__ == "__main__":
    for root, degree, name in P11_CASES:
        result = run_p11(root, degree)
        print(f"--- {name} ---")
        print(f"Branch: {result['branch']}")
        print(f"Div(q) count: {result['div_q_count']}")
        print(f"Contradiction: {result['contradiction']}")
        print("State atoms:")
        for atom in sorted(result["state"], key=repr):
            print(f"  {atom!r}")
        print()
