"""P28 scoped observability and refusal dashboard.

Aggregates verified, scope-preserving observations without changing runtime
decisions or collapsing local evidence into global qualification.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

DECISIONS = {"EXECUTE", "REFUSE", "INCONCLUSIVE", "UNKNOWN"}
REFUSAL_CAUSES = {
    "EXECUTION_BLOCKED",
    "POLICY_VIOLATION",
    "UNSUPPORTED_PAYLOAD",
}
SCOPE_FIELDS = ("model_id", "task_id", "profile_id", "experiment_id", "evidence_version")


def _scope(record: Mapping[str, Any]) -> tuple[Any, ...]:
    missing = [field for field in SCOPE_FIELDS if field not in record]
    if missing:
        raise ValueError(f"missing scope fields: {', '.join(missing)}")
    return tuple(record[field] for field in SCOPE_FIELDS)


def _entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    return -sum((n / total) * math.log2(n / total) for n in counts.values() if n)


class DashboardAggregator:
    """Compute P28 invariants independently for each evidence scope."""

    def aggregate(self, records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        grouped: defaultdict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
        for record in records:
            decision = record.get("decision")
            if decision not in DECISIONS:
                raise ValueError(f"invalid decision: {decision!r}")
            grouped[_scope(record)].append(record)

        return [self._aggregate_scope(scope, rows) for scope, rows in sorted(grouped.items(), key=str)]

    def _aggregate_scope(
        self, scope: tuple[Any, ...], rows: list[Mapping[str, Any]]
    ) -> dict[str, Any]:
        verified = [r for r in rows if r["decision"] in {"EXECUTE", "REFUSE"}]
        decisions = Counter(r["decision"] for r in verified)
        total = len(verified)
        refusals = decisions["REFUSE"]

        causes = Counter(
            r["refusal_cause"]
            for r in rows
            if r["decision"] == "REFUSE" and r.get("refusal_cause") in REFUSAL_CAUSES
        )
        known_refusals = sum(causes.values())
        refusal_distribution = {
            cause: count / known_refusals for cause, count in sorted(causes.items())
        }

        repeated = Counter(
            (r.get("task_instance_id"), r["decision"])
            for r in verified
            if r.get("task_instance_id") is not None
        )
        task_counts = Counter(r["task_instance_id"] for r in verified if r.get("task_instance_id") is not None)
        comparable_tasks = sum(1 for count in task_counts.values() if count > 1)
        stable_tasks = sum(
            1
            for task_id in task_counts
            if len({decision for (candidate_task, decision) in repeated if candidate_task == task_id})
            == 1
            and task_counts[task_id] > 1
        )
        stability = stable_tasks / comparable_tasks if comparable_tasks else None

        boundaries = []
        for task_id in sorted(task_counts, key=str):
            outcomes = {decision for (candidate_task, decision) in repeated if candidate_task == task_id}
            if len(outcomes) > 1:
                boundaries.append({"task_instance_id": task_id, "outcomes": sorted(outcomes)})

        if not verified:
            decisions_present = {r["decision"] for r in rows}
            state = "UNKNOWN" if decisions_present == {"UNKNOWN"} else "INCONCLUSIVE"
        elif stability is None and comparable_tasks == 0:
            state = "INCONCLUSIVE"
        else:
            state = "VERIFIED"

        return {
            "scope": dict(zip(SCOPE_FIELDS, scope, strict=True)),
            "state": state,
            "decision_count": total,
            "execute_count": decisions["EXECUTE"],
            "refuse_count": refusals,
            "execute_ratio": decisions["EXECUTE"] / total if total else None,
            "refuse_ratio": refusals / total if total else None,
            "refusal_cause_distribution": refusal_distribution,
            "decision_entropy_bits": _entropy(decisions),
            "capability_stability": stability,
            "capability_boundaries": boundaries,
        }


__all__ = ["DashboardAggregator", "DECISIONS", "REFUSAL_CAUSES", "SCOPE_FIELDS"]
