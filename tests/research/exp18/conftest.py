"""Shared EXP-18 research fixtures."""

from __future__ import annotations

import pytest

from research.exp18.conflict_node import AtomicObservation
from research.exp18.dag_aggregator import build_dag


@pytest.fixture
def sample_r0_ledger():
    sources = (
        (
            AtomicObservation(
                object_ref="obj_01",
                property="status",
                val_curr="green",
                provenance="prov-ai-1",
            ),
            AtomicObservation(
                object_ref="obj_02",
                property="status",
                val_curr="red",
                provenance="prov-ai-1",
            ),
        ),
        (
            AtomicObservation(
                object_ref="obj_01",
                property="status",
                val_curr="red",
                provenance="prov-ai-2",
            ),
            AtomicObservation(
                object_ref="obj_02",
                property="status",
                val_curr="red",
                provenance="prov-ai-2",
            ),
        ),
        (
            AtomicObservation(
                object_ref="obj_01",
                property="status",
                val_curr="green",
                provenance="prov-human",
            ),
            AtomicObservation(
                object_ref="obj_02",
                property="status",
                val_curr="green",
                provenance="prov-human",
            ),
        ),
    )
    return build_dag(sources)
