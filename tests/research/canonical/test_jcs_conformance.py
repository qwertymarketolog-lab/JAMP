"""RFC 8785 conformance tests against fixed canonical-byte vectors.

These diagnostic tests intentionally run in the default suite. Failures are
preserved as evidence that the current serializer is not yet JCS-conformant.
"""

from __future__ import annotations

import json

import pytest

from jamp.research.canonical import canonical_bytes
from tests.research.canonical.jcs_vectors import CONFORMANCE_VECTORS


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
