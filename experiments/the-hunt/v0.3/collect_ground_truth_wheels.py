"""Collect pinned The Hunt wheels and an offline dependency wheelhouse."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TARGETS: dict[str, dict[str, str]] = {
    "celery": {
        "version": "5.6.3",
        "filename": "celery-5.6.3-py3-none-any.whl",
        "sha256": "0808f42f80909c4d5833202360ffafb2a4f83f4d8e23e1285d926610e9a7afa6",
    },
    "httpx": {
        "version": "0.28.1",
        "filename": "httpx-0.28.1-py3-none-any.whl",
        "sha256": "d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59ad",
    },
    "requests": {
        "version": "2.34.2",
        "filename": "requests-2.34.2-py3-none-any.whl",
        "sha256": "2a0d60c172f83ac6ab31e4554906c0f3b3588d37b5cb939b1c061f4907e278e0",
    },
}
SCHEMA_VERSION = "jamp.hunt.wheelhouse.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def collect(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    wheelhouse = output_dir / "wheelhouse"
    target_wheels = output_dir / "target_wheels"
    if wheelhouse.exists() and any(wheelhouse.iterdir()):
        raise FileExistsError(f"refusing to reuse non-empty wheelhouse: {wheelhouse}")
    wheelhouse.mkdir(parents=True, exist_ok=True)
    target_wheels.mkdir(parents=True, exist_ok=True)

    requirements = [f"{name}=={item['version']}" for name, item in TARGETS.items()]
    command = [
        sys.executable, "-m", "pip", "download",
        "--disable-pip-version-check", "--no-cache-dir",
        "--only-binary=:all:", "--dest", str(wheelhouse), *requirements,
    ]
    print("WHEEL_DOWNLOAD_COMMAND: " + " ".join(command), flush=True)
    subprocess.run(command, check=True)

    wheel_files = sorted(wheelhouse.glob("*.whl"))
    if not wheel_files:
        raise RuntimeError("pip download produced no wheel files")
    if len(wheel_files) != len({path.name for path in wheel_files}):
        raise RuntimeError("duplicate wheel filenames in wheelhouse")

    target_records: dict[str, dict[str, str]] = {}
    for package, pin in TARGETS.items():
        matches = [path for path in wheel_files if path.name == pin["filename"]]
        if len(matches) != 1:
            raise RuntimeError(
                f"{package}: expected exactly one {pin['filename']}, found {len(matches)}"
            )
        wheel_path = matches[0]
        observed = sha256_file(wheel_path)
        if observed != pin["sha256"]:
            raise RuntimeError(
                f"{package}: wheel SHA-256 mismatch; "
                f"expected={pin['sha256']} observed={observed}"
            )
        shutil.copy2(wheel_path, target_wheels / wheel_path.name)
        target_records[package] = {
            "version": pin["version"],
            "filename": wheel_path.name,
            "sha256": observed,
            "wheelhouse_path": wheel_path.name,
            "target_copy_path": f"target_wheels/{wheel_path.name}",
        }
        print(
            f"TARGET_WHEEL_VERIFIED: {package}=={pin['version']} sha256={observed}",
            flush=True,
        )

    wheelhouse_records = [
        {
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in wheel_files
    ]
    pip_version = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "collector": {
            "python": sys.version,
            "platform": platform.platform(),
            "pip": pip_version,
        },
        "targets": target_records,
        "wheelhouse": wheelhouse_records,
        "wheelhouse_count": len(wheelhouse_records),
        "dependency_resolution": (
            "pip download --only-binary=:all:; dependency wheel versions are "
            "captured in this run's manifest, not treated as cross-run pins"
        ),
    }
    _write_json(output_dir / "wheel_manifest.json", manifest)
    print(
        f"WHEELHOUSE_MANIFEST: {output_dir / 'wheel_manifest.json'} "
        f"wheel_count={len(wheelhouse_records)}",
        flush=True,
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    collect(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
