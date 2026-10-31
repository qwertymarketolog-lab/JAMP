"""Differential JCS checks against the python-jcs reference package.

Install the project dev extra, then run the tests. A missing reference
implementation or Hypothesis dependency must fail collection, not silently
skip the independent comparison.
"""
from __future__ import annotations

import jcs
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from jamp.research.canonical import canonical_bytes
from tests.research.canonical.jcs_vectors import CONFORMANCE_VECTORS


def _reference_bytes(value) -> bytes:
    result = jcs.canonicalize(value)
    return result if isinstance(result, bytes) else result.encode("utf-8")


@pytest.mark.parametrize("vector", CONFORMANCE_VECTORS, ids=[v.id for v in CONFORMANCE_VECTORS])
def test_matches_reference_vectors(vector) -> None:
    import json

    value = json.loads(vector.input)
    assert canonical_bytes(value) == _reference_bytes(value)


_json_scalars = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-(2**53 - 1), max_value=2**53 - 1)
    | st.floats(allow_nan=False, allow_infinity=False, width=64)
    | st.text()
)
_json_values = st.recursive(
    _json_scalars,
    lambda children: st.lists(children, max_size=5)
    | st.dictionaries(st.text(), children, max_size=5),
    max_leaves=20,
)


@given(_json_values)
@settings(max_examples=100, derandomize=True)
def test_random_json_matches_reference(value) -> None:
    assert canonical_bytes(value) == _reference_bytes(value)
