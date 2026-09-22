"""EXP-22 v0 GREEN compliance tests for the current runtime implementation."""

from __future__ import annotations

import math

import pytest

from jamp.atomic_observation import create_atomic_observation


def _make_atom(**overrides):
    values = {
        "content": "alpha",
        "atom_type": "text_token",
        "source_ref": "sha256:source",
        "operator_id": "exp22.reference",
        "operator_version": "1.0",
        "params": {"mode": "token"},
    }
    values.update(overrides)
    return create_atomic_observation(**values)


def test_determinism() -> None:
    assert _make_atom().id == _make_atom().id


def test_payload_sensitivity() -> None:
    assert _make_atom().id != _make_atom(content="beta").id


def test_source_binding() -> None:
    assert (
        _make_atom(source_ref="sha256:source-a").id != _make_atom(source_ref="sha256:source-b").id
    )


def test_transcript_boundaries() -> None:
    assert (
        _make_atom(params={"mode": "token", "segment_index": 0}).id
        != _make_atom(params={"mode": "token", "segment_index": 1}).id
    )


def test_identity_separation() -> None:
    left_a = _make_atom(content="left", params={"component": "A"}).id
    left_b = _make_atom(content="left", params={"component": "A"}).id
    right_a = _make_atom(content="right", params={"component": "B"}).id
    right_b = _make_atom(content="mutated-right", params={"component": "B"}).id

    assert left_a == left_b
    assert right_a != right_b


def test_semantic_neutrality() -> None:
    atom = _make_atom()
    public_values = {str(value).upper() for value in atom.__dict__.values()}
    assert not ({"SUPPORTED", "REJECTED", "INCONCLUSIVE"} & public_values)


@pytest.mark.parametrize(
    "payload",
    [
        {"verdict": "SUPPORTED"},
        {"supported": True},
        {"rejected": False},
        {"confidence": 0.99},
        {"nested": [{"verdict": "REJECTED"}]},
    ],
)
def test_semantic_verdict_keys_fail_closed(payload) -> None:
    with pytest.raises(ValueError):
        _make_atom(content=payload)


def test_closed_identity_params_ignore_operational_noise() -> None:
    base = _make_atom(params={"segment_index": 3, "mode": "token"})
    changed = _make_atom(params={"segment_index": 3, "mode": "other"})
    assert base.id == changed.id


def test_canonical_json_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError):
        _make_atom(content={"value": math.nan})


@pytest.mark.parametrize("source_ref", ["", 1, None])
def test_source_ref_validation(source_ref) -> None:
    with pytest.raises(ValueError):
        _make_atom(source_ref=source_ref)
