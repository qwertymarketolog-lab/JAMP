"""Deterministic base-ref resolution and race protection for Research Loop v0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from decision import Decision

_SHA_RE = __import__("re").compile(r"[0-9a-fA-F]{40}")


@dataclass(frozen=True)
class BaseResolution:
    decision: Decision
    base_ref: str
    resolved_sha: str | None
    reason: str


def resolve_base_sha(
    *,
    base_ref: str,
    expected_base_sha: str | None,
    require_head_match: bool,
    ref_resolver: Callable[[str], str | None],
) -> BaseResolution:
    if not base_ref.strip():
        return BaseResolution(
            Decision.INCONCLUSIVE, base_ref, None, "missing base_ref"
        )

    if require_head_match and not expected_base_sha:
        return BaseResolution(
            Decision.INCONCLUSIVE,
            base_ref,
            None,
            "missing expected_base_sha",
        )

    try:
        resolved_sha = ref_resolver(base_ref)
    except Exception as exc:  # fail closed at the boundary
        return BaseResolution(
            Decision.INCONCLUSIVE,
            base_ref,
            None,
            f"base_ref resolution failed: {type(exc).__name__}",
        )

    if resolved_sha is None or not _SHA_RE.fullmatch(resolved_sha):
        return BaseResolution(
            Decision.INCONCLUSIVE,
            base_ref,
            resolved_sha,
            "resolver returned invalid SHA",
        )

    if expected_base_sha and resolved_sha.lower() != expected_base_sha.lower():
        return BaseResolution(
            Decision.INCONCLUSIVE,
            base_ref,
            resolved_sha,
            "base_ref changed from expected_base_sha",
        )

    return BaseResolution(
        Decision.ALLOW,
        base_ref,
        resolved_sha,
        "base_ref resolved and matched",
    )
