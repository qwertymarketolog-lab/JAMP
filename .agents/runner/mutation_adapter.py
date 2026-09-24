"""Execution boundary for already-authorized mutations."""

from __future__ import annotations

from dataclasses import dataclass

from operation_policy import Authorization


@dataclass(frozen=True)
class MutationResult:
    attempted: bool
    success: bool
    resulting_ref_or_commit: str | None


def apply(authorization: Authorization) -> MutationResult:
    """Execute an authorized mutation.

    This v0 adapter is deliberately inert: policy acceptance is separated
    from real repository mutation. The caller must provide an Authorization
    produced after ALLOW.
    """
    if not isinstance(authorization, Authorization):
        raise TypeError("apply() requires Authorization")

    return MutationResult(
        attempted=True,
        success=False,
        resulting_ref_or_commit=None,
    )


__all__ = ["MutationResult", "apply"]
