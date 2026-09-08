"""P17.6 contract tests for autonomous closed-loop experiments and reporting."""

import json

import pytest

from jamp.p17.closed_loop import ClosedLoopExperiment, ExperimentResult
from jamp.p17.experiment_report import (
    canonical_report_json,
    compute_report_digest,
    render_cli,
    serialize_report,
    verify_report,
    write_report,
)


def test_closed_loop_runs_multiple_generations():
    result = ClosedLoopExperiment(generations=4).run()
    assert isinstance(result, ExperimentResult)
    assert len(result.iterations) == 4


def test_baseline_starts_from_uniform_floor_policy():
    result = ClosedLoopExperiment(generations=1).run()
    baseline = result.iterations[0]
    assert baseline.policy.values == (("exploit", 0.1), ("explore", 0.1))


def test_policy_evolves_only_from_internal_feedback():
    result = ClosedLoopExperiment(generations=4).run()
    assert result.iterations[0].policy_digest != result.iterations[-1].policy_digest
    assert all(item.evidence_source == "pattern_index" for item in result.iterations[1:])


def test_causal_efficiency_has_positive_directional_gain():
    result = ClosedLoopExperiment(generations=4).run()
    assert result.iterations[-1].causal_efficiency > result.iterations[0].causal_efficiency
    assert result.delta_causal_efficiency > 0.0


def test_exploration_floor_survives_every_generation():
    result = ClosedLoopExperiment(generations=5).run()
    for item in result.iterations:
        assert all(value >= item.policy.min_weight for value in item.policy.as_dict().values())


def test_replay_matches_policy_used_by_each_iteration():
    result = ClosedLoopExperiment(generations=4).run()
    assert result.replay_verified is True
    assert all(item.replay_policy_digest == item.policy_digest for item in result.iterations)


def test_completed_trajectory_digests_are_immutable_and_distinct_when_policy_changes():
    result = ClosedLoopExperiment(generations=4).run()
    digests = [item.trajectory_digest for item in result.iterations]
    assert len(set(digests)) == len(digests)


def test_redundant_search_branches_do_not_increase():
    result = ClosedLoopExperiment(generations=5).run()
    burdens = [item.branching_burden for item in result.iterations]
    assert burdens[-1] <= burdens[0]


def test_invalid_generation_count_is_rejected():
    with pytest.raises(ValueError):
        ClosedLoopExperiment(generations=0)


def test_report_contains_empirical_generation_matrix_and_causal_chain():
    report = ClosedLoopExperiment(generations=4).run().report()
    assert report["schema_version"] == "1.0"
    assert len(report["generations"]) == 4
    assert len(report["causal_chain"]["events"]) == 3
    assert report["generations"][0]["policy_weights"] == [["exploit", 0.1], ["explore", 0.1]]
    assert report["generations"][0]["policy_event_id"] == "GENESIS"
    assert report["generations"][1]["policy_event_id"] == "POLICY_0001"
    assert report["summary"]["baseline_causal_efficiency"] == report["generations"][0]["causal_efficiency"]
    assert report["summary"]["final_causal_efficiency"] == report["generations"][-1]["causal_efficiency"]


def test_report_digest_is_deterministic_and_verifiable():
    report = ClosedLoopExperiment(generations=4).run().report()
    assert verify_report(report)
    assert report["report_digest"] == compute_report_digest(report)
    assert canonical_report_json(report) == canonical_report_json(dict(report))
    assert serialize_report(report) == canonical_report_json(report)


def test_report_tampering_is_rejected():
    report = ClosedLoopExperiment(generations=4).run().report()
    tampered = dict(report)
    tampered["summary"] = dict(report["summary"])
    tampered["summary"]["final_causal_efficiency"] = 999.0
    assert verify_report(tampered) is False
    with pytest.raises(ValueError):
        serialize_report(tampered)


def test_cli_is_a_pure_projection_of_the_sealed_report():
    report = ClosedLoopExperiment(generations=4).run().report()
    cli = render_cli(report)
    assert "P17.6 CLOSED-LOOP EXPERIMENT" in cli
    assert "GEN | POLICY" in cli
    assert f"Report digest: {report['report_digest']}" in cli
    assert str(report["generations"][-1]["trajectory_digest"][:16]) in cli


def test_report_json_is_parseable_and_writeable(tmp_path):
    report = ClosedLoopExperiment(generations=4).run().report()
    serialized = serialize_report(report)
    assert json.loads(serialized) == report
    destination = write_report(report, tmp_path / "experiment_report.json")
    assert destination.read_text(encoding="utf-8").rstrip("\n") == serialized
