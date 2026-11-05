"""Regression tests for deterministic package provenance scoring."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from jamp.server.checks import provenance


def _metadata(age_days: int, project_urls=None, author="Maintainer"):
    now = datetime(2026, 11, 3, tzinfo=UTC)
    first = now - timedelta(days=age_days)
    return now, {
        "info": {
            "project_urls": project_urls or {"Source": "https://github.com/example/pkg"},
            "author": author,
            "author_email": "",
        },
        "releases": {"1.0": [{"upload_time_iso_8601": first.isoformat()}]},
    }


def test_age_penalty_boundaries_are_preserved():
    expected = {29: (50, 50), 30: (20, 80), 364: (20, 80), 365: (0, 100)}
    for age, (penalty, score) in expected.items():
        now, payload = _metadata(age)
        result = provenance._score_metadata("samplepkg", payload, now)
        assert result["evidence"]["age_penalty"] == penalty
        assert result["trust_score"] == score


def test_missing_release_dates_are_inconclusive():
    result = provenance._score_metadata(
        "samplepkg", {"info": {"author": "A", "project_urls": {}}, "releases": {"1.0": []}}
    )
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "missing_dates"


def test_homepage_does_not_count_as_repository():
    now, payload = _metadata(365, {"Homepage": "https://example.com"})
    result = provenance._score_metadata("samplepkg", payload, now)
    assert result["evidence"]["repository_present"] is False
    assert result["trust_score"] == 70


def test_http_404_is_not_found():
    with patch.object(provenance, "fetch_pypi_json", return_value=(404, None)):
        result = provenance.check_provenance("missing-pkg")
    assert result["status"] == "NOT_FOUND"
