from research.exp18.atomic_observation import (
    ALLOWED_TYPES,
    AtomicObservation,
    create_atomic_observation,
)


def make_atom(**overrides):
    values = {
        "content": "alpha",
        "atom_type": "text_token",
        "source_ref": "sha256:source",
        "operator_id": "exp18.reference",
        "operator_version": "0.1",
        "params": {"mode": "token"},
    }
    values.update(overrides)
    return create_atomic_observation(**values)


def test_contract_exposes_required_fields():
    atom = make_atom()

    assert isinstance(atom, AtomicObservation)
    assert atom.id
    assert atom.content == "alpha"
    assert atom.type in ALLOWED_TYPES
    assert atom.source_ref == "sha256:source"
    assert atom.provenance["input_hash"] == atom.source_ref
    assert atom.provenance["operator"] == {
        "id": "exp18.reference",
        "version": "0.1",
    }
    assert atom.provenance["params"] == {"mode": "token"}
    assert atom.parent_link == {
        "root_hash": atom.source_ref,
        "parent_id": None,
    }


def test_atom_id_is_deterministic():
    assert make_atom() == make_atom()


def test_atom_id_changes_when_identity_input_changes():
    baseline = make_atom()
    changed = make_atom(params={"mode": "character"})

    assert baseline.id != changed.id
