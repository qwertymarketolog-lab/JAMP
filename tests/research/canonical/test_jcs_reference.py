"""Differential JCS checks against the optional python-jcs reference package.

Install the project extra/reference dependency in a dedicated verification
environment, then run with JAMP_RUN_JCS_CONFORMANCE=1. Missing reference
implementation is an explicit skip, never a conformance pass.
"""
from __future__ import annotations

import os

import pytest

jcs = pytest.importorskip("jcs", reason="python-jcs reference package is not installed")
hypothesis = pytest.importorskip("hypothesis", reason="Hypothesis is not installed")

from hypothesis import given, settings, strategies as st

from jamp.research.canonical import canonical_bytes
from tests.research.canonical.jcs_vectors import CONFORMANCE_VECTORS

pytestmark = pytest.mark.skipif(
    os.getenv("JAMP_RUN_JCS_CONFORMANCE") != "1",
    reason="differential JCS harness is opt-in; conformance remains pending",
)


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
