"""EXP-22 atomic-observation integrity RED-state harness.

The harness targets the current production/runtime namespace (src/jamp).
It deliberately does not import historical EXP-18 research implementations:
those are evidence objects, not proof of the current runtime state.

RED is established when the current runtime cannot provide the required
AtomicObservation identity contract. GREEN requires the same six tests to
execute against a current-runtime implementation.
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any

import pytest


RUNTIME_MODULE = "jamp.atomic_observation"


def _runtime_api() -> Any:
    """Load the current runtime atomic-observation API, fail closed if absent."""
    try:
        return importlib.import_module(RUNTIME_MODULE)
    except ModuleNotFoundError as exc:
        pytest.fail(
            "RED: current runtime has no atomic-observation module "
            f"{RUNTIME_MODULE!r}; historical EXP-18 research code is not "
            "accepted as current-runtime evidence."
        )
        raise AssertionError from exc


def _make_atom(**overrides: Any) -> Any:
    api = _runtime_api()
    factory = getattr(api, "create_atomic_observation", None)
    if not callable(factory):
        pytest.fail(
            "RED: current runtime atomic-observation module does not expose "
            "create_atomic_observation()."
        )

    values = {
        "content": "alpha",
        "atom_type": "text_token",
        "source_ref": "sha256:source",
        "operator_id": "exp22.reference",
        "operator_version": "1.0",
        "params": {"mode": "token"},
    }
    values.update(overrides)
    return factory(**values)


def _identity(atom: Any) -> str:
    value = getattr(atom, "id", None)
    assert isinstance(value, str) and value, "RED: atomic identity is missing"
    return value


def test_determinism() -> None:
    """Unchanged atomization yields the same identity."""
    assert _identity(_make_atom()) == _identity(_make_atom())


def test_payload_sensitivity() -> None:
    """Changing atomic payload changes identity."""
    baseline = _identity(_make_atom())
    changed = _identity(_make_atom(content="beta"))
    assert baseline != changed


def test_source_binding() -> None:
    """Changing source binding changes identity."""
    baseline = _identity(_make_atom(source_ref="sha256:source-a"))
    changed = _identity(_make_atom(source_ref="sha256:source-b"))
    assert baseline != changed


def test_transcript_boundaries() -> None:
    """Changing boundary-defining input changes identity."""
    baseline = _identity(_make_atom(params={"mode": "token", "segment_index": 0}))
    changed = _identity(_make_atom(params={"mode": "token", "segment_index": 1}))
    assert baseline != changed


def test_identity_separation() -> None:
    """A composite mutation cannot mask an unchanged component identity."""
    left_a = _identity(_make_atom(content="left", params={"component": "A"}))
    left_b = _identity(_make_atom(content="left", params={"component": "A"}))
    right_a = _identity(_make_atom(content="right", params={"component": "B"}))
    right_b = _identity(_make_atom(content="mutated-right", params={"component": "B"}))

    assert left_a == left_b
    assert right_a != right_b


def test_semantic_neutrality() -> None:
    """Atomization payload exposes no semantic evaluation verdict."""
    atom = _make_atom()
    public = getattr(atom, "__dict__", {})
    forbidden = {"SUPPORTED", "REJECTED", "INCONCLUSIVE"}

    values = {str(value).upper() for value in public.values()}
    keys = {str(key).upper() for key in public.keys()}

    assert not (forbidden & values)
    assert not any("VERDICT" in key for key in keys)

    # Keep the check structural rather than depending on a private
    # implementation detail.
    signature = inspect.signature(type(atom))
    assert "verdict" not in {name.lower() for name in signature.parameters}
