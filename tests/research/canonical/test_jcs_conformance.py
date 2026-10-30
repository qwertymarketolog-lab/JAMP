"""Opt-in RFC 8785 conformance probes.

The current canonical.py is not assumed to be JCS. Keep this diagnostic
harness out of the blocking default suite until a reference-backed decision
is made. Run explicitly with JAMP_RUN_JCS_CONFORMANCE=1.
"""
from __future__ import annotations

import json
import os

import pytest

from jamp.research.canonical import canonical_bytes
from tests.research.canonical.jcs_vectors import CONFORMANCE_VECTORS

pytestmark = pytest.mark.skipif(
    os.getenv("JAMP_RUN_JCS_CONFORMANCE") != "1",
    reason="diagnostic JCS harness is opt-in; conformance remains pending",
)


@pytest.mark.parametrize("vector", CONFORMANCE_VECTORS, ids=[v.id for v in CONFORMANCE_VECTORS])
def test_vector_matches_expected(vector) -> None:
    parsed = json.loads(vector.input)
    actual = canonical_bytes(parsed)
    assert actual == vector.expected, (
        f"{vector.id}: {vector.note}\n"
        f"input={vector.input!r}\nexpected={vector.expected!r}\nactual={actual!r}"
    )


@pytest.mark.parametrize("vector", CONFORMANCE_VECTORS, ids=[v.id for v in CONFORMANCE_VECTORS])
def test_canonicalization_is_idempotent(vector) -> None:
    parsed = json.loads(vector.input)
    once = canonical_bytes(parsed)
    twice = canonical_bytes(json.loads(once))
    assert once == twice, f"{vector.id}: canonicalization is not idempotent"
