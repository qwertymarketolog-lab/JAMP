"""R0 tests for EXP-18 Phase #4 ConflictNode v0."""

from __future__ import annotations

from dataclasses import replace

from research.exp18.conflict_node import (
    AtomicObservation,
    CollisionType,
    EpistemicStatus,
    classify,
)


def atom(source: str, value: object, *, property_name: str = "status") -> AtomicObservation:
    return AtomicObservation(
        object_ref="object-1",
        property=property_name,
        val_curr=value,
        provenance=f"prov-{source}",
    )


def test_all_sources_identical_set_is_agreement() -> None:
    sources = (
        (atom("ai-1", "green"), atom("ai-1", 7, property_name="count")),
        (atom("ai-2", "green"), atom("ai-2", 7, property_name="count")),
        (atom("human", "green"), atom("human", 7, property_name="count")),
    )

    result = classify(sources)

    assert result.status is EpistemicStatus.AGREEMENT
    assert result.collision is CollisionType.AGREEMENT
    assert result.discrepancies == ()


def test_value_conflict_is_inconclusive_without_majority_oracle() -> None:
    sources = (
        (atom("ai-1", "green"),),
        (atom("ai-2", "red"),),
        (atom("human", "green"),),
    )

    result = classify(sources)

    assert result.status is EpistemicStatus.INCONCLUSIVE
    assert result.collision is CollisionType.CONFLICT
    assert result.discrepancies[0]["reason"] == "VALUE_MISMATCH"
    assert result.discrepancies[0]["values"] == ("'green'", "'red'")


def test_missing_comparable_atom_is_inconclusive() -> None:
    sources = (
        (atom("ai-1", "green"), atom("ai-1", 7, property_name="count")),
        (atom("ai-2", "green"),),
        (atom("human", "green"), atom("human", 7, property_name="count")),
    )

    result = classify(sources)

    assert result.status is EpistemicStatus.INCONCLUSIVE
    assert result.discrepancies[0]["reason"] == "MISSING_COMPARABLE_ATOM"


def test_source_order_does_not_change_verdict_or_discrepancies() -> None:
    sources = (
        (atom("ai-1", "green"),),
        (atom("ai-2", "red"),),
        (atom("human", "green"),),
    )

    first = classify(sources)
    second = classify((sources[2], sources[0], sources[1]))

    assert first.status is second.status
    assert first.collision is second.collision
    assert first.discrepancies == second.discrepancies


def test_provenance_is_preserved_in_output() -> None:
    sources = (
        (atom("ai-1", "green"),),
        (atom("ai-2", "red"),),
        (atom("human", "green"),),
    )

    result = classify(sources)

    assert result.provenance == ("prov-ai-1", "prov-ai-2", "prov-human")


def test_atomic_observation_is_immutable() -> None:
    observation = atom("ai-1", "green")

    try:
        observation.val_curr = "red"
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("AtomicObservation must be immutable")

    assert replace(observation, val_curr="red").val_curr == "red"
