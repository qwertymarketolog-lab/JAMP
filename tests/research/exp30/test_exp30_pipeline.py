"""EXP-30: scale atomic decomposition from N=5 to N=10."""

from __future__ import annotations

from dataclasses import replace

import pytest

from .atomic_decomposer import decompose_all, has_semantic_claim, reconstruct
from .dataset_exp30_loader import ZERO_INDICES, load_exp30_observations, source_ref


def _source_refs() -> tuple[str, ...]:
    return tuple(source_ref(index) for index in ZERO_INDICES)


def test_exp30_a_b_captures_exactly_ten_deterministically() -> None:
    observations = load_exp30_observations()
    first = decompose_all(observations, _source_refs())
    second = decompose_all(observations, _source_refs())

    assert len(observations) == 10
    assert len(first) == 10
    assert first == second
    assert [atom.zero_index for atom in first] == list(range(1, 11))


def test_exp30_c_preserves_lineage_for_all_indices() -> None:
    atoms = decompose_all(load_exp30_observations(), _source_refs())
    assert [atom.source_ref for atom in atoms] == [source_ref(i) for i in range(1, 11)]
    assert [atom.observation_id for atom in atoms] == [source_ref(i) for i in range(1, 11)]


def test_exp30_d_reconstructs_all_ten_observations_exactly() -> None:
    observations = load_exp30_observations()
    atoms = decompose_all(observations, _source_refs())
    assert [reconstruct(atom) for atom in atoms] == list(observations)


def test_exp30_e_identity_control_has_no_semantic_claims() -> None:
    atoms = decompose_all(load_exp30_observations(), _source_refs())
    assert all(not has_semantic_claim(atom) for atom in atoms)


def test_exp30_e_value_tamper_z7_is_detectable() -> None:
    atom = decompose_all(load_exp30_observations(), _source_refs())[6]
    tampered = replace(atom, imag_part=atom.imag_part + "0")
    assert tampered != atom
    assert reconstruct(tampered) != reconstruct(atom)


def test_exp30_e_provenance_tamper_is_detectable() -> None:
    atom = decompose_all(load_exp30_observations(), _source_refs())[6]
    tampered = replace(atom, source_ref="exp30:zero_index=999")
    assert tampered.source_ref != atom.source_ref
    assert tampered.observation_id == atom.observation_id


def test_exp30_e_semantic_injection_is_detectable() -> None:
    atom = decompose_all(load_exp30_observations(), _source_refs())[0]
    injected = replace(
        atom,
        metadata=atom.metadata + (("claim", "Riemann Hypothesis is proved"),),
    )
    assert has_semantic_claim(injected) is True


def test_exp30_e_cardinality_mismatch_fails_closed() -> None:
    observations = load_exp30_observations()
    with pytest.raises(ValueError, match="equal length"):
        decompose_all(observations, _source_refs()[:-1])
