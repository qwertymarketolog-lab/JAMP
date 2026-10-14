from scripts.agents.daily_evidence_agent import event_delta


def test_initial_baseline_does_not_claim_new_events() -> None:
    current = {"pull_requests": [{"number": 1}], "workflow_runs": [{"id": 10}]}

    result = event_delta(current, None)

    assert result == {
        "mode": "INITIAL_BASELINE",
        "new_or_updated_prs": [],
        "new_or_updated_runs": [],
    }


def test_event_delta_detects_new_and_updated_items() -> None:
    previous = {
        "pull_requests": {"1": "2026-10-13T10:00:00Z"},
        "workflow_runs": {"10:1": "2026-10-13T10:00:00Z"},
    }
    current = {
        "pull_requests": [
            {"number": 1, "updated_at": "2026-10-14T10:00:00Z"},
            {"number": 2, "updated_at": "2026-10-14T11:00:00Z"},
        ],
        "workflow_runs": [
            {"id": 10, "run_attempt": 1, "updated_at": "2026-10-14T10:00:00Z"},
            {"id": 11, "run_attempt": 1, "updated_at": "2026-10-14T11:00:00Z"},
        ],
    }

    result = event_delta(current, previous)

    assert [item["number"] for item in result["new_or_updated_prs"]] == [1, 2]
    assert [item["id"] for item in result["new_or_updated_runs"]] == [10, 11]


def test_event_delta_ignores_unchanged_items() -> None:
    previous = {
        "pull_requests": {"1": "2026-10-14T10:00:00Z"},
        "workflow_runs": {"10:1": "2026-10-14T10:00:00Z"},
    }
    current = {
        "pull_requests": [{"number": 1, "updated_at": "2026-10-14T10:00:00Z"}],
        "workflow_runs": [{"id": 10, "run_attempt": 1, "updated_at": "2026-10-14T10:00:00Z"}],
    }

    result = event_delta(current, previous)

    assert result["new_or_updated_prs"] == []
    assert result["new_or_updated_runs"] == []
