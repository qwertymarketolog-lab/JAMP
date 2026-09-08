"""Canonical, verifiable reporting for P17.6 closed-loop experiments."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

REPORT_SCHEMA_VERSION = "1.0"
_REPORT_DIGEST_FIELD = "report_digest"


def canonical_report_json(report: Mapping[str, Any]) -> str:
    return json.dumps(dict(report), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _unsigned_report(report: Mapping[str, Any]) -> dict[str, Any]:
    unsigned = dict(report)
    unsigned[_REPORT_DIGEST_FIELD] = None
    return unsigned


def compute_report_digest(report: Mapping[str, Any]) -> str:
    payload = canonical_report_json(_unsigned_report(report)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def seal_report(report: Mapping[str, Any]) -> dict[str, Any]:
    sealed = _unsigned_report(report)
    sealed[_REPORT_DIGEST_FIELD] = compute_report_digest(sealed)
    return sealed


def verify_report(report: Mapping[str, Any]) -> bool:
    digest = report.get(_REPORT_DIGEST_FIELD)
    return isinstance(digest, str) and digest == compute_report_digest(report)


def serialize_report(report: Mapping[str, Any]) -> str:
    if not verify_report(report):
        raise ValueError("experiment report digest verification failed")
    return canonical_report_json(report)


def render_cli(report: Mapping[str, Any]) -> str:
    if not verify_report(report):
        raise ValueError("experiment report digest verification failed")
    generations = report["generations"]
    lines = [
        "P17.6 CLOSED-LOOP EXPERIMENT",
        "GEN | POLICY                  | CE       | BRANCH | TRAJECTORY",
        "----+-------------------------+----------+--------+----------------",
    ]
    for item in generations:
        policy = ", ".join(f"{name}={value:.6g}" for name, value in item["policy_weights"])
        lines.append(
            f"{item['generation']:>3} | {policy:<23} | "
            f"{item['causal_efficiency']:>8.6f} | "
            f"{item['branching_burden']:>6} | {item['trajectory_digest'][:16]}"
        )
    summary = report["summary"]
    lines.extend([
        "",
        f"ΔCE: {summary['delta_causal_efficiency']:.6f}",
        f"Trajectory divergence: {summary['trajectory_divergence']}",
        f"Exploration floor preserved: {summary['exploration_floor_preserved']}",
        f"Replay verified: {summary['replay_verified']}",
        f"Internal feedback only: {summary['internal_feedback_only']}",
        f"Report digest: {report['report_digest']}",
    ])
    return "\n".join(lines)


def build_report(result: Any) -> dict[str, Any]:
    iterations = result.iterations
    if not iterations:
        raise ValueError("cannot build report from an empty experiment result")
    generations: list[dict[str, Any]] = []
    for item in iterations:
        generations.append({
            "generation": item.generation,
            "policy_weights": [[name, value] for name, value in item.policy.values],
            "policy_digest": item.policy_digest,
            "policy_event_id": item.policy_event_id,
            "causal_efficiency": item.causal_efficiency,
            "cost": item.cost,
            "branching_burden": item.branching_burden,
            "pattern_digest": item.pattern_digest,
            "evidence_source": item.evidence_source,
            "replay_policy_digest": item.replay_policy_digest,
            "replay_verified": item.replay_policy_digest == item.policy_digest,
            "trajectory_digest": item.trajectory_digest,
        })
    events = [
        {
            "event_id": event["event_id"],
            "parent_id": event["parent_id"],
            "previous_policy_digest": event["previous_policy_digest"],
            "new_policy_digest": event["new_policy_digest"],
            "evidence_digest": event["evidence_digest"],
            "policy_update_digest": event["policy_update_digest"],
        }
        for event in result.causal_chain
    ]
    baseline = generations[0]
    final = generations[-1]
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "experiment": "P17.6 closed-loop experiments",
        "generations": generations,
        "causal_chain": {"events": events},
        "summary": {
            "delta_causal_efficiency": result.delta_causal_efficiency,
            "trajectory_divergence": len({item["trajectory_digest"] for item in generations}) == len(generations),
            "exploration_floor_preserved": all(
                all(value >= item.policy.min_weight for _, value in item.policy.values)
                for item in iterations
            ),
            "replay_verified": result.replay_verified,
            "internal_feedback_only": all(
                item["evidence_source"] == "baseline" if item["generation"] == 0 else item["evidence_source"] == "pattern_index"
                for item in generations
            ),
            "baseline_causal_efficiency": baseline["causal_efficiency"],
            "final_causal_efficiency": final["causal_efficiency"],
        },
        "report_digest": None,
    }
    return seal_report(report)


def write_report(report: Mapping[str, Any], path: str | Path) -> Path:
    serialized = serialize_report(report)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(serialized + "\n", encoding="utf-8")
    return destination


def _load_report(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        report = json.load(handle)
    if not isinstance(report, dict):
        raise ValueError("experiment report root must be a JSON object")
    return report


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify or render a canonical P17.6 experiment report.")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--verify", metavar="FILE", help="verify the report SHA-256 seal")
    actions.add_argument("--render", metavar="FILE", help="render the verified report as CLI output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_cli_parser().parse_args(argv)
    path = args.verify or args.render
    report = _load_report(path)
    if args.verify:
        if not verify_report(report):
            print("INVALID: experiment report digest verification failed")
            return 1
        print(f"VALID: {report['report_digest']}")
        return 0
    print(render_cli(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
