"""EXP-18 R1 contract tests: red phase for atomic observation semantics."""

import pytest

from research.exp18.atomic_observation import (
    AtomicObservation,
    AtomicObservationError,
    create_atomic_observation,
)


def make_atom(**overrides):
    values = {
        "content": "Plant X changed after treatment Y.",
        "atom_type": "semantic_chunk",
        "source_ref": "sha256:raw-input-001",
        "operator_id": "exp18.decomposer",
        "operator_version": "1.0",
        "params": {"mode": "statement"},
    }
    values.update(overrides)
    return create_atomic_observation(**values)


def test_01_provenance_is_required_and_id_is_hash_derived():
    atom = make_atom()
    assert atom.source_ref
    assert atom.provenance["input_hash"] == atom.source_ref
    assert len(atom.id) == 64
    with pytest.raises(AtomicObservationError):
        make_atom(source_ref="")


def test_02_identity_changes_when_source_or_content_changes():
    baseline = make_atom()
    assert baseline.id != make_atom(source_ref="sha256:raw-input-002").id
    assert baseline.id != make_atom(content="Plant X did not change.").id


def test_03_source_identity_is_explicit():
    atom = make_atom(source_id="model_alpha")
    assert atom.source_id == "model_alpha"


def test_04_atomic_subject_event_value_are_explicit():
    atom = make_atom(
        subject="Plant X",
        event="changed",
        value="after treatment Y",
    )
    assert atom.subject == "Plant X"
    assert atom.event == "changed"
    assert atom.value == "after treatment Y"


@pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
def test_05_confidence_is_bounded(confidence):
    atom = make_atom(confidence=confidence)
    assert atom.confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_05b_confidence_out_of_range_is_rejected(confidence):
    with pytest.raises(AtomicObservationError):
        make_atom(confidence=confidence)


def test_06_parent_and_root_lineage_are_preserved():
    root = make_atom()
    child = make_atom(parent_id=root.id)
    assert child.parent_link["root_hash"] == root.source_ref
    assert child.parent_link["parent_id"] == root.id


def test_07_atom_has_no_epistemic_supported_verdict():
    atom = make_atom()
    assert isinstance(atom, AtomicObservation)
    assert not hasattr(atom, "epistemic_status") or atom.epistemic_status == "RAW_ATOM"
    assert not getattr(atom, "supported", False)


def test_08_identical_input_is_deterministic():
    assert make_atom() == make_atom()


def test_09_provenance_or_input_mutation_changes_identity():
    baseline = make_atom()
    changed_operator = make_atom(operator_version="1.1")
    changed_source = make_atom(source_ref="sha256:raw-input-009")
    assert baseline.id != changed_operator.id
    assert baseline.id != changed_source.id


def test_10_conflicting_atom_sets_remain_inconclusive():
    from research.exp18.conflict_node import (
        AtomicObservation as ConflictAtom,
        EpistemicStatus,
        classify,
    )

    left = ConflictAtom(
        object_ref="Plant X",
        property="status",
        val_curr="changed",
        provenance="sha256:left",
    )
    right = ConflictAtom(
        object_ref="Plant X",
        property="status",
        val_curr="unchanged",
        provenance="sha256:right",
    )
    result = classify(((left,), (right,)))
    assert result.status == EpistemicStatus.INCONCLUSIVE
    assert result.collision is not None
