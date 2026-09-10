#!/usr/bin/env python3
"""Generate a deterministic, dependency-free CycloneDX JSON SBOM from pyproject.toml."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import tomllib


ROOT = pathlib.Path(__file__).resolve().parents[1]


def component(name: str, version: str, scope: str) -> dict[str, str]:
    return {"type": "library", "name": name, "version": version, "scope": scope}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="sbom.cdx.json")
    args = parser.parse_args()
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    components: list[dict[str, str]] = []
    for dep in project.get("dependencies", []):
        name, _, version = dep.partition(">=")
        components.append(component(name.strip(), version.strip() or "unspecified", "required"))
    for dep in project.get("optional-dependencies", {}).get("dev", []):
        name, _, version = dep.partition(">=")
        components.append(component(name.strip(), version.strip() or "unspecified", "development"))
    components.sort(key=lambda item: (item["scope"], item["name"], item["version"]))
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:jamp-local-sbom",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": project["name"], "version": project["version"]}},
        "components": components,
    }
    payload = json.dumps(bom, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    bom["metadata"]["properties"] = [{"name": "jamp.sbom.sha256", "value": hashlib.sha256(payload).hexdigest()}]
    out = ROOT / args.output
    out.write_text(json.dumps(bom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
