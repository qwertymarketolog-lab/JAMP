"""H-J3 P0: pure syntactic canonicalization for mathematical ASTs.

This module deliberately performs representation-only transformations.
It does not evaluate expressions, apply algebraic identities, invoke solvers,
or perform semantic equivalence checking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, TypeAlias


@dataclass(frozen=True, slots=True)
class Variable:
    name: str


@dataclass(frozen=True, slots=True)
class Constant:
    value: int | str


@dataclass(frozen=True, slots=True)
class Unary:
    op: str
    child: "Expr"


@dataclass(frozen=True, slots=True)
class Binary:
    op: str
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True, slots=True)
class Relation:
    op: str
    left: "Expr"
    right: "Expr"


Expr: TypeAlias = Variable | Constant | Unary | Binary | Relation

_ASSOCIATIVE_COMMUTATIVE: Final[frozenset[str]] = frozenset({"+", "*"})
_COMMUTATIVE: Final[frozenset[str]] = frozenset({"+", "*"})
_SYMMETRIC_RELATIONS: Final[frozenset[str]] = frozenset()


def _structural_key(expr: Expr) -> tuple:
    if isinstance(expr, Variable):
        return ("Variable", expr.name)
    if isinstance(expr, Constant):
        return ("Constant", type(expr.value).__name__, expr.value)
    if isinstance(expr, Unary):
        return ("Unary", expr.op, _structural_key(expr.child))
    if isinstance(expr, Binary):
        return ("Binary", expr.op, _structural_key(expr.left), _structural_key(expr.right))
    if isinstance(expr, Relation):
        return ("Relation", expr.op, _structural_key(expr.left), _structural_key(expr.right))
    raise TypeError(f"unsupported expression type: {type(expr).__name__}")


def structural_key(expr: Expr) -> tuple:
    """Return the deterministic lexical key used by canonicalization."""
    return _structural_key(canonicalize(expr))


def _flatten(op: str, expr: Expr) -> list[Expr]:
    if isinstance(expr, Binary) and expr.op == op:
        return _flatten(op, expr.left) + _flatten(op, expr.right)
    return [expr]


def _fold(op: str, terms: list[Expr]) -> Expr:
    if not terms:
        raise ValueError("cannot fold an empty operator sequence")
    result = terms[0]
    for term in terms[1:]:
        result = Binary(op, result, term)
    return result


def canonicalize(expr: Expr) -> Expr:
    """Return the pure syntactic canonical form of *expr*.

    Only registered representation symmetries are changed.  In particular,
    no arithmetic evaluation or identity reduction is performed.
    """
    if isinstance(expr, Variable | Constant):
        return expr

    if isinstance(expr, Unary):
        return Unary(expr.op, canonicalize(expr.child))

    if isinstance(expr, Binary):
        left = canonicalize(expr.left)
        right = canonicalize(expr.right)

        if expr.op in _ASSOCIATIVE_COMMUTATIVE:
            terms = _flatten(expr.op, left) + _flatten(expr.op, right)
            terms.sort(key=_structural_key)
            return _fold(expr.op, terms)

        if expr.op in _COMMUTATIVE:
            if _structural_key(right) < _structural_key(left):
                left, right = right, left
            return Binary(expr.op, left, right)

        # Non-commutative operators such as subtraction/division preserve order.
        return Binary(expr.op, left, right)

    if isinstance(expr, Relation):
        left = canonicalize(expr.left)
        right = canonicalize(expr.right)
        if expr.op in _SYMMETRIC_RELATIONS and _structural_key(right) < _structural_key(left):
            left, right = right, left
        return Relation(expr.op, left, right)

    raise TypeError(f"unsupported expression type: {type(expr).__name__}")


__all__ = [
    "Binary",
    "Constant",
    "Expr",
    "Relation",
    "Unary",
    "Variable",
    "canonicalize",
    "structural_key",
]
