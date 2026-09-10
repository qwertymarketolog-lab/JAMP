#!/usr/bin/env python3
"""Offline baseline integrity check for contributor workflows."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default=os.environ.get("JAMP_BASELINE_SHA"))
    args = parser.parse_args()
    if not args.baseline:
        print("ERROR: JAMP_BASELINE_SHA/--baseline is required; no baseline is invented.", file=sys.stderr)
        return 2
    try:
        baseline = git("rev-parse", "--verify", f"{args.baseline}^{{commit}}")
        head = git("rev-parse", "HEAD")
        subprocess.run(["git", "merge-base", "--is-ancestor", baseline, head], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: baseline check failed: {exc}", file=sys.stderr)
        return 1
    unstaged = git("diff", "--name-only")
    untracked = git("ls-files", "--others", "--exclude-standard")
    if unstaged or untracked:
        print("ERROR: unstaged or untracked changes are present; stage or remove them before publishing.", file=sys.stderr)
        if unstaged:
            print("unstaged:", unstaged, file=sys.stderr)
        if untracked:
            print("untracked:", untracked, file=sys.stderr)
        return 1
    print(f"BASELINE_OK baseline={baseline} head={head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
