"""Falsifiable R1 tests for the research-only EXP-18 DAG query layer."""

from __future__ import annotations

from research.exp18.conflict_node import AtomicObservation
from research.exp18.dag_aggregator import build_dag
from research.exp18.dag_query import query_subgraph


def atom(
    source: str,
    object_ref: str,
    property: str,
    value: object,
) -> AtomicObservation:
    return AtomicObservation(
        object_ref=object_ref,
        property=property,
        val_curr=value,
        provenance=f"prov-{source}",
    )


def make_dag():
    sources = (
        (
            atom("ai-1", "obj_01", "status", "green"),
            atom("ai-1", "obj_02", "status", "red"),
        ),
        (
            atom("ai-2", "obj_01", "status", "red"),
            atom("ai-2", "obj_02", "status", "red"),
        ),
        (
            atom("human", "obj_01", "status", "green"),
            atom("human", "obj_02", "status", "green"),
        ),
    )
    return build_dag(sources)


def test_tc_q01_exact_object_slice() -> None:
    result = query_subgraph(make_dag(), object_ref="obj_01")

    assert result
    assert all(item["object_ref"] == "obj_01" for item in result)


def test_tc_q02_property_slice_is_deterministic() -> None:
    dag = make_dag()

    first = query_subgraph(dag, property="status")
    second = query_subgraph(dag, property="status")

    assert first == second
    assert first == tuple(
        sorted(
            first,
            key=lambda item: (
                item["object_ref"],
                item["property"],
                item["provenance"],
            ),
        )
    )


def test_tc_q03_provenance_isolation() -> None:
    result = query_subgraph(make_dag(), provenance="prov-ai-1")

    assert result
    assert all(item["provenance"] == "prov-ai-1" for item in result)


def test_tc_q04_discrepancy_type_isolation() -> None:
    result = query_subgraph(make_dag(), discrepancy_type="CONFLICT")

    assert result
    assert all(item["discrepancy_type"] == "CONFLICT" for item in result)
    assert {(item["object_ref"], item["property"]) for item in result} == {
        ("obj_01", "status"),
        ("obj_02", "status"),
    }


def test_tc_q05_anti_scoring_invariant() -> None:
    result = query_subgraph(make_dag())

    forbidden = {"score", "confidence", "rank", "voting_weight"}

    assert result
    assert all(forbidden.isdisjoint(item) for item in result)


def test_tc_q06_replay_determinism() -> None:
    dag = make_dag()

    first = query_subgraph(
        dag,
        object_ref="obj_01",
        property="status",
    )
    second = query_subgraph(
        dag,
        object_ref="obj_01",
        property="status",
    )

    assert first == second
