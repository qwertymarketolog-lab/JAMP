#!/usr/bin/env python3
"""Fail-closed verifier for the JAMP Core Integrity Contract v0."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


EXPECTED_CONTRACT = "CIC-v0"
EXPECTED_HASH_SCHEME = "git-blob-sha1"
FAILURE = 2


def fail(message: str) -> int:
    print(f"CORE_INTEGRITY_VIOLATION: {message}", file=sys.stderr)
    return FAILURE


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def git_revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def load_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load manifest: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")
    if manifest.get("contract_version") != EXPECTED_CONTRACT:
        raise ValueError("unsupported contract_version")
    if manifest.get("core_id") != "JAMP-FROZEN-CORE":
        raise ValueError("unexpected core_id")
    if manifest.get("hash_scheme") != EXPECTED_HASH_SCHEME:
        raise ValueError("unsupported hash_scheme")
    entries = manifest.get("canonical_files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("canonical_files must be a non-empty list")
    return manifest


def verify(root: Path, manifest_path: Path) -> int:
    try:
        manifest = load_manifest(manifest_path)
        revision = git_revision(root)
        entries = manifest["canonical_files"]

        for entry in entries:
            if not isinstance(entry, dict):
                return fail("canonical entry is not an object")
            rel = entry.get("path")
            expected = entry.get("git_blob_sha1")
            if not isinstance(rel, str) or not isinstance(expected, str):
                return fail("canonical entry has invalid path or hash")
            if len(expected) != 40:
                return fail(f"{rel}: canonical Git blob SHA-1 must be 40 hex characters")

            target = (root / rel).resolve()
            if root.resolve() not in target.parents:
                return fail(f"{rel}: path escapes repository root")
            if not target.is_file():
                return fail(f"{rel}: canonical file is missing")

            observed = git_blob_sha1(target)
            if observed != expected:
                return fail(f"{rel}: expected {expected}, observed {observed}")

            print(f"PASS {rel} git_blob_sha1={observed}")

        print(f"PASS CIC-v0 contract={EXPECTED_CONTRACT} revision={revision}")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        return fail(str(exc))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "integrity"
        / "core-manifest-v0.json",
    )
    args = parser.parse_args()
    return verify(args.root.resolve(), args.manifest.resolve())


if __name__ == "__main__":
    sys.exit(main())
