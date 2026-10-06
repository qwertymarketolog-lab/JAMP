from src.jamp.observability.dashboard import DashboardAggregator


def record(**overrides):
    base = {
        "model_id": "m1",
        "task_id": "t1",
        "profile_id": "p1",
        "experiment_id": "e1",
        "evidence_version": "v1",
        "decision": "EXECUTE",
        "task_instance_id": "i1",
    }
    base.update(overrides)
    return base


def test_decision_ratio_and_entropy():
    result = DashboardAggregator().aggregate(
        [record(decision="EXECUTE", task_instance_id="i1"),
         record(decision="REFUSE", refusal_cause="POLICY_VIOLATION", task_instance_id="i2")]
    )[0]

    assert result["execute_ratio"] == 0.5
    assert result["refuse_ratio"] == 0.5
    assert result["decision_entropy_bits"] == 1.0


def test_refusal_cause_distribution_excludes_unknown_causes():
    result = DashboardAggregator().aggregate(
        [
            record(decision="REFUSE", refusal_cause="POLICY_VIOLATION", task_instance_id="i1"),
            record(decision="REFUSE", refusal_cause="EXECUTION_BLOCKED", task_instance_id="i2"),
            record(decision="REFUSE", refusal_cause="NOT_IN_CONTRACT", task_instance_id="i3"),
        ]
    )[0]

    assert result["refusal_cause_distribution"] == {
        "EXECUTION_BLOCKED": 0.5,
        "POLICY_VIOLATION": 0.5,
    }


def test_capability_stability_and_boundary():
    result = DashboardAggregator().aggregate(
        [
            record(task_instance_id="repeat-a", decision="EXECUTE"),
            record(task_instance_id="repeat-a", decision="EXECUTE"),
            record(task_instance_id="repeat-b", decision="EXECUTE"),
            record(
                task_instance_id="repeat-b",
                decision="REFUSE",
                refusal_cause="POLICY_VIOLATION",
            ),
        ]
    )[0]

    assert result["capability_stability"] == 0.5
    assert result["capability_boundaries"] == [
        {"task_instance_id": "repeat-b", "outcomes": ["EXECUTE", "REFUSE"]}
    ]


def test_unknown_and_inconclusive_are_not_decisions():
    aggregator = DashboardAggregator()

    unknown = aggregator.aggregate([record(decision="UNKNOWN")])[0]
    assert unknown["state"] == "UNKNOWN"
    assert unknown["decision_count"] == 0
    assert unknown["execute_ratio"] is None
    assert unknown["refuse_ratio"] is None

    inconclusive = aggregator.aggregate([record(decision="INCONCLUSIVE")])[0]
    assert inconclusive["state"] == "INCONCLUSIVE"
    assert inconclusive["decision_count"] == 0


def test_scope_cannot_be_collapsed():
    results = DashboardAggregator().aggregate(
        [
            record(model_id="m1", task_instance_id="i1"),
            record(model_id="m2", task_instance_id="i2"),
        ]
    )

    assert len(results) == 2
    assert {r["scope"]["model_id"] for r in results} == {"m1", "m2"}


def test_missing_scope_is_rejected():
    invalid = record()
    del invalid["profile_id"]

    try:
        DashboardAggregator().aggregate([invalid])
    except ValueError as exc:
        assert "profile_id" in str(exc)
    else:
        raise AssertionError("missing scope must fail closed")
