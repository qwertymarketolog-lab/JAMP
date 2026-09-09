"""End-to-End Synthetic Discovery Benchmark E2E-1A (SPEC-E2E-1-SYNTHETIC-DISCOVERY-1.0.0)."""

import pytest

from jamp.research.hypothesis_scoring import score_hypothesis
from tests.benchmarks.fixtures.e2e_synthetic_discovery import (
    create_tick_1_fixture,
    create_tick_2_fixture,
    create_tick_3_fixture,
)


def test_e2e_1a_tick_1_baseline_score():
    """Tick 1: Verify baseline score for H1 with single node and single source."""
    fixture = create_tick_1_fixture()
    score = score_hypothesis(fixture.hypothesis_h1, fixture.ledger, fixture.graph)
    assert score == pytest.approx(fixture.expected_score_h1, abs=1e-12)
    assert score == pytest.approx(5.0 / 6.0, abs=1e-12)


def test_e2e_1a_tick_2_expansion_and_sibling_competing_score():
    """Tick 2: Verify expanded H1 score and competing H2 score."""
    fixture = create_tick_2_fixture()
    score_h1 = score_hypothesis(fixture.hypothesis_h1, fixture.ledger, fixture.graph)
    score_h2 = score_hypothesis(fixture.hypothesis_h2, fixture.ledger, fixture.graph)

    assert score_h1 == pytest.approx(fixture.expected_score_h1, abs=1e-12)
    assert score_h1 == pytest.approx(8.0 / 9.0, abs=1e-12)
    assert score_h2 == pytest.approx(fixture.expected_score_h2, abs=1e-12)
    assert score_h2 == pytest.approx(13.0 / 18.0, abs=1e-12)
    assert score_h1 > score_h2


def test_e2e_1a_tick_3_corrupt_evidence_rejection():
    """Tick 3: Verify corrupt evidence is rejected without positive scoring."""
    fixture = create_tick_3_fixture()
    with pytest.raises(ValueError):
        score_hypothesis(fixture.hypothesis_h3, fixture.ledger, fixture.graph)
