"""H-J3 O4: pure symbolic bound propagation.

O4 narrows explicitly supplied symbolic bounds. It does not enumerate
values, generate tuples, evaluate expressions, or invoke an external solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, NamedTuple

from .p0_canonical import Expr


class Interval(NamedTuple):
    variable: Expr
    lower: Expr
    lower_closed: bool
    upper: Expr
    upper_closed: bool


class TightenResult(NamedTuple):
    interval: Interval | None
    contradiction: bool
    parents: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BoundState:
    """Immutable symbolic bound state keyed by statement identifier."""

    statements: tuple[tuple[str, Expr], ...] = ()


@dataclass(frozen=True, slots=True)
class DerivedBound:
    """One locally derived bound and its immediate provenance parents."""

    statement_id: str
    expression: Expr | Interval
    parents: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PropagationResult:
    """Immutable result of one pure O4 propagation pass."""

    state: BoundState
    derived: tuple[DerivedBound, ...] = ()
    contradiction: bool = False


_ALLOWED_RELATIONS: Final[frozenset[str]] = frozenset({"<", "<=", ">", ">="})


def _as_bound(expr: Expr) -> tuple[Expr, str, Expr] | None:
    """Recognize only a symbolic variable-vs-constant inequality token."""
    from .p0_canonical import Constant, Relation, Variable

    if not isinstance(expr, Relation) or expr.op not in _ALLOWED_RELATIONS:
        return None
    if isinstance(expr.left, Variable) and isinstance(expr.right, Constant):
        return expr.left, expr.op, expr.right
    if isinstance(expr.right, Variable) and isinstance(expr.left, Constant):
        reverse = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}
        return expr.right, reverse[expr.op], expr.left
    return None


def _tighten(
    variable: Expr,
    bounds: list[tuple[str, str, Expr]],
) -> TightenResult:
    """Derive one symbolic interval without evaluating endpoint expressions."""
    lowers = [(sid, op, value) for sid, op, value in bounds if op in (">", ">=")]
    uppers = [(sid, op, value) for sid, op, value in bounds if op in ("<", "<=")]
    if not lowers or not uppers:
        return TightenResult(None, False, ())

    # This v0.1 engine intentionally compares only identical constant tokens.
    # It therefore never performs arithmetic evaluation or numeric ordering.
    for lower_sid, lop, endpoint in lowers:
        upper_sid = next((sid for sid, _, value in uppers if value == endpoint), None)
        if upper_sid is None:
            continue

        lower_strict = any(op == ">" for _, op, value in lowers if value == endpoint)
        upper_strict = any(op == "<" for _, op, value in uppers if value == endpoint)

        if lower_strict or upper_strict:
            return TightenResult(None, True, ())

        return TightenResult(Interval(variable, endpoint, True, endpoint, True), False, (lower_sid, upper_sid))

    return TightenResult(None, False, ())


def propagate_bounds(
    state: BoundState,
    constraints: list[Expr],
) -> PropagationResult:
    """Perform one symbolic-only O4 propagation pass.

    Constraints are treated as existing statement tokens. No discrete domain
    is materialized, no tuple/product is generated, and no solver is called.
    Derived statements require explicit parent IDs from the current state.
    """
    if not isinstance(state, BoundState):
        raise TypeError("state must be a BoundState")

    normalized = tuple(constraints)
    indexed = list(state.statements)
    known = {sid: expr for sid, expr in indexed}
    next_id = len(indexed)
    derived: list[DerivedBound] = []
    derived_next_id = 0
    contradiction = False

    by_variable: dict[Expr, list[tuple[str, str, Expr]]] = {}
    for sid, expr in indexed:
        parsed = _as_bound(expr)
        if parsed is not None:
            variable, op, value = parsed
            by_variable.setdefault(variable, []).append((sid, op, value))

    for expr in normalized:
        parsed = _as_bound(expr)
        if parsed is None:
            continue
        variable, op, value = parsed
        sid = f"o4-input-{next_id}"
        next_id += 1
        if sid not in known:
            indexed.append((sid, expr))
            known[sid] = expr
        by_variable.setdefault(variable, []).append((sid, op, value))

    for variable, bounds in by_variable.items():
        local_result = _tighten(variable, bounds)
        contradiction = contradiction or local_result.contradiction
        if local_result.interval is not None:
            derived.append(DerivedBound(statement_id=f"o4-derived-{derived_next_id}", expression=local_result.interval, parents=local_result.parents))
            derived_next_id += 1

    # v0.1 records supplied constraints and derives symbolic intervals
    # without numeric evaluation or domain materialization.
    result_state = BoundState(tuple(indexed))
    return PropagationResult(result_state, tuple(derived), contradiction)


__all__ = ["BoundState", "Interval", "DerivedBound", "PropagationResult", "propagate_bounds"]
