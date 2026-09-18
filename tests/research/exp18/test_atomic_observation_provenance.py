import pytest

from research.exp18.atomic_observation import (
    AtomicObservationError,
    create_atomic_observation,
)


def test_source_ref_is_required():
    with pytest.raises(AtomicObservationError, match="source_ref"):
        create_atomic_observation(
            content="alpha",
            atom_type="text_token",
            source_ref="",
            operator_id="exp18.reference",
            operator_version="0.1",
            params={},
        )


@pytest.mark.parametrize(
    ("operator_id", "operator_version"),
    [("", "0.1"), ("exp18.reference", "")],
)
def test_operator_identity_is_required(operator_id, operator_version):
    with pytest.raises(
        AtomicObservationError,
        match="operator id and version",
    ):
        create_atomic_observation(
            content="alpha",
            atom_type="text_token",
            source_ref="sha256:source",
            operator_id=operator_id,
            operator_version=operator_version,
            params={},
        )


def test_atom_type_is_constrained():
    with pytest.raises(AtomicObservationError, match="unsupported atom type"):
        create_atomic_observation(
            content="alpha",
            atom_type="unknown",
            source_ref="sha256:source",
            operator_id="exp18.reference",
            operator_version="0.1",
            params={},
        )


def test_parent_link_preserves_root_and_parent():
    atom = create_atomic_observation(
        content="alpha",
        atom_type="semantic_chunk",
        source_ref="sha256:root",
        operator_id="exp18.reference",
        operator_version="0.1",
        params={},
        parent_id="parent-001",
    )

    assert atom.parent_link == {
        "root_hash": "sha256:root",
        "parent_id": "parent-001",
    }
