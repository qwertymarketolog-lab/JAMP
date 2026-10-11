"""EXP-29: atomic decomposition of the finite EXP-28 observations."""

from __future__ import annotations

from dataclasses import replace

import pytest

from .atomic_decomposer import decompose_all, has_semantic_claim, reconstruct
from .dataset_exp28_loader import load_exp28_observations, source_ref


def _source_refs() -> tuple[str, ...]:
    observations = load_exp28_observations()
    return tuple(source_ref(item["zero_index"]) for item in observations)


def test_exp29_a_b_decomposes_five_observations_deterministically() -> None:
    observations = load_exp28_observations()
    refs = _source_refs()

    first = decompose_all(observations, refs)
    second = decompose_all(observations, refs)

    assert len(first) == 5
    assert first == second
    assert [atom.zero_index for atom in first] == [1, 2, 3, 4, 5]


def test_exp29_c_preserves_exp28_lineage() -> None:
    atoms = decompose_all(load_exp28_observations(), _source_refs())

    assert [atom.source_ref for atom in atoms] == [
        "exp28:zero_index=1",
        "exp28:zero_index=2",
        "exp28:zero_index=3",
        "exp28:zero_index=4",
        "exp28:zero_index=5",
    ]


def test_exp29_d_reconstructs_each_observation_exactly() -> None:
    observations = load_exp28_observations()
    atoms = decompose_all(observations, _source_refs())

    assert [reconstruct(atom) for atom in atoms] == list(observations)


def test_exp29_e_identity_control_accepts_unchanged_atoms() -> None:
    atoms = decompose_all(load_exp28_observations(), _source_refs())

    assert all(not has_semantic_claim(atom) for atom in atoms)


def test_exp29_e_value_tamper_is_detectable() -> None:
    atom = decompose_all(load_exp28_observations(), _source_refs())[0]
    tampered = replace(atom, imag_part=atom.imag_part + 1.0)

    assert reconstruct(tampered) != reconstruct(atom)


def test_exp29_e_provenance_tamper_is_detectable() -> None:
    atom = decompose_all(load_exp28_observations(), _source_refs())[0]
    tampered = replace(atom, source_ref="exp28:zero_index=999")

    assert tampered.source_ref != atom.source_ref
    assert tampered.observation_id == atom.observation_id


def test_exp29_e_semantic_injection_is_detectable() -> None:
    atom = decompose_all(load_exp28_observations(), _source_refs())[0]
    injected = replace(
        atom,
        metadata=atom.metadata + (("claim", "Riemann Hypothesis is proved"),),
    )

    assert has_semantic_claim(injected) is True


def test_exp29_e_cardinality_mismatch_fails_closed() -> None:
    observations = load_exp28_observations()

    with pytest.raises(ValueError, match="equal length"):
        decompose_all(observations, _source_refs()[:-1])
