#!/usr/bin/env python3
"""Run Track A through the D1–D8 adapter and export RunResult as JSON.

Viewer-facing artifact generator. Does not modify Track A or the Run
contract. Reuses the existing adapter implementation
(tests/research/track_a_run_adapter.py) rather than reimplementing D1–D8.

Usage:
    PYTHONPATH=src python scripts/export_run_result.py \
        --root 2 --seed 42 --N 500 --max-objects 120 \
        --out run_result.json

Output schema:
    source              "track_a_run_adapter"
    adapter_contract    "D1-D8"
    run_contract        "v0.3"
    commit              git HEAD sha, or null
    environment         python, platform
    input               root, seed, N, max_objects
    run_result          steps, iterations, stop_reason{kind, detail}
    track_a_history_len len(state.history)
    final_size          len(state.objects)
    trace               [{step, op, parents, expr}, ...]
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_adapter():
    """Try both common import styles for the adapter."""
    try:
        from tests.research.track_a_run_adapter import run_track_a_via_adapter
        return run_track_a_via_adapter
    except ImportError:
        pass
    sys.path.insert(0, str(_ROOT / "tests" / "research"))
    try:
        from track_a_run_adapter import run_track_a_via_adapter
        return run_track_a_via_adapter
    except ImportError as exc:
        print(f"error: cannot import adapter: {exc}", file=sys.stderr)
        print("hint: run with PYTHONPATH=src from project root", file=sys.stderr)
        sys.exit(2)


def _git_commit():
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def _expr_str(e):
    return e if isinstance(e, str) else str(e)


def _serialize_trace(history):
    out = []
    for i, entry in enumerate(history):
        if isinstance(entry, dict):
            out.append({
                "step": entry.get("step", i),
                "op": entry.get("op", ""),
                "parents": list(entry.get("parents", [])),
                "expr": _expr_str(entry.get("expr", "")),
            })
        else:
            out.append({
                "step": i,
                "op": str(getattr(entry, "op", "")),
                "parents": list(getattr(entry, "parents", [])),
                "expr": _expr_str(getattr(entry, "expr", "")),
            })
    return out


def main():
    p = argparse.ArgumentParser(description="Track A -> RunResult JSON export")
    p.add_argument("--root", type=int, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--N", type=int, default=500)
    p.add_argument("--max-objects", type=int, default=120, dest="max_objects")
    p.add_argument("--out", type=str, default="-",
                   help='output path, or "-" for stdout')
    args = p.parse_args()

    run_track_a_via_adapter = _load_adapter()
    result = run_track_a_via_adapter(args.root, args.seed, args.N, args.max_objects)

    state = result.state
    history = list(getattr(state, "history", []))
    objects = list(getattr(state, "objects", []))

    artifact = {
        "source": "track_a_run_adapter",
        "adapter_contract": "D1-D8",
        "run_contract": "v0.3",
        "commit": _git_commit(),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "input": {
            "root": args.root,
            "seed": args.seed,
            "N": args.N,
            "max_objects": args.max_objects,
        },
        "run_result": {
            "steps": result.steps,
            "iterations": result.iterations,
            "stop_reason": {
                "kind": result.stop_reason.kind,
                "detail": result.stop_reason.detail,
            },
        },
        "track_a_history_len": len(history),
        "final_size": len(objects),
        "trace": _serialize_trace(history),
    }

    text = json.dumps(artifact, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
