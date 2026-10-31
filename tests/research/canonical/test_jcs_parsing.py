"""Strict JSON parsing boundary tests for JCS-compatible numeric/key handling."""
from __future__ import annotations

import json
import math

import pytest

from tests.research.canonical.jcs_vectors import (
    V3A_UNSAFE_INTEGER,
    V3B_FLOAT_OVERFLOW,
    V7_DUPLICATE_KEYS,
)

_MAX_SAFE_INTEGER = (2**53) - 1


def _parse_int(token: str) -> int:
    value = int(token)
    if abs(value) > _MAX_SAFE_INTEGER:
        raise ValueError(f"integer outside IEEE-754 safe range: {token}")
    return value


def _parse_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"non-finite JSON number: {token}")
    return value


def _reject_constant(token: str):
    raise ValueError(f"non-JSON numeric constant: {token}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def strict_json_loads(payload: bytes):
    return json.loads(
        payload,
        parse_int=_parse_int,
        parse_float=_parse_float,
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_object,
    )


def test_v3a_unsafe_integer_is_rejected_without_precision_loss() -> None:
    with pytest.raises(ValueError, match="safe range"):
        strict_json_loads(V3A_UNSAFE_INTEGER)


def test_v3b_float_overflow_is_rejected_before_canonicalization() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        strict_json_loads(V3B_FLOAT_OVERFLOW)


def test_v7_duplicate_json_keys_are_rejected_at_parse_boundary() -> None:
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        strict_json_loads(V7_DUPLICATE_KEYS)


def test_safe_integer_is_preserved_exactly() -> None:
    assert strict_json_loads(b"9007199254740991") == _MAX_SAFE_INTEGER
