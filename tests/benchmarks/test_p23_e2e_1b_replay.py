"""Cold Replay Benchmark E2E-1B (SPEC-E2E-1B-COLD-REPLAY-HARNESS-1.0.0).

Verifies exact bitwise equality between online calculations and fresh process
reconstructions loaded from disk artifacts.
"""

from pathlib import Path

import pytest

from jamp.research.hypothesis_scoring import score_hypothesis
from tests.benchmarks.fixtures.e2e_synthetic_discovery import (
    create_tick_1_fixture,
    create_tick_2_fixture,
    create_tick_3_fixture,
)
from tests.benchmarks.harness.cold_replay_runner import run_cold_replay


def test_e2e_1b_tick_1_cold_replay_exact_match(tmp_path: Path):
    """Verify Tick 1 H1 score reconstructed in isolated process matches online score bitwise."""
    fixture = create_tick_1_fixture()

    online_score_h1 = score_hypothesis(
        fixture.hypothesis_h1, fixture.ledger, fixture.graph
    )

    cold_results = run_cold_replay(
        graph=fixture.graph,
        ledger=fixture.ledger,
        hypotheses=[fixture.hypothesis_h1],
        tmp_path=tmp_path / "tick1",
    )

    cold_score_h1 = cold_results["H1"]

    assert cold_score_h1 == online_score_h1
    assert cold_score_h1 == pytest.approx(5.0 / 6.0, abs=1e-12)


def test_e2e_1b_tick_2_cold_replay_exact_match(tmp_path: Path):
    """Verify Tick 2 H1 and H2 scores reconstructed in isolated process match online scores."""
    fixture = create_tick_2_fixture()

    online_score_h1 = score_hypothesis(
        fixture.hypothesis_h1, fixture.ledger, fixture.graph
    )
    online_score_h2 = score_hypothesis(
        fixture.hypothesis_h2, fixture.ledger, fixture.graph
    )

    cold_results = run_cold_replay(
        graph=fixture.graph,
        ledger=fixture.ledger,
        hypotheses=[fixture.hypothesis_h1, fixture.hypothesis_h2],
        tmp_path=tmp_path / "tick2",
    )

    assert cold_results["H1"] == online_score_h1
    assert cold_results["H2"] == online_score_h2

    assert cold_results["H1"] == pytest.approx(8.0 / 9.0, abs=1e-12)
    assert cold_results["H2"] == pytest.approx(13.0 / 18.0, abs=1e-12)
    assert cold_results["H1"] > cold_results["H2"]


def test_e2e_1b_tick_3_cold_replay_exception_isolation(tmp_path: Path):
    """Verify that corrupt evidence exception is properly captured across subprocess boundary."""
    fixture = create_tick_3_fixture()

    # Tick 3 captures the exact locked production exception from evidence.py.
    with pytest.raises(ValueError, match="evidence record integrity mismatch"):
        run_cold_replay(
            graph=fixture.graph,
            ledger=fixture.ledger,
            hypotheses=[fixture.hypothesis_h3],
            tmp_path=tmp_path / "tick3",
        )
