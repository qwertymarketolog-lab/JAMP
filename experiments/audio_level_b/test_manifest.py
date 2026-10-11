"""Structural and optional local-byte checks for the isolated ArtifactNet manifest."""

import hashlib
import json
import re
from pathlib import Path

MANIFEST_PATH = Path(__file__).parent / "model_manifest.json"
REQUIRED_TOP_LEVEL = {
    "model_name",
    "version",
    "source_repository",
    "source_url",
    "revision_id",
    "license",
    "identity_gate_status",
    "local_verification_status",
    "components",
}
REQUIRED_COMPONENT_FIELDS = {
    "file_name",
    "role",
    "expected_size_bytes",
    "expected_sha256",
    "local_verification_status",
}


def test_artifactnet_manifest():
    assert MANIFEST_PATH.is_file(), (
        "model_manifest.json not found in experiments/audio_level_b/"
    )

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert REQUIRED_TOP_LEVEL <= manifest.keys()
    assert manifest["model_name"] == "ArtifactNet"
    assert manifest["identity_gate_status"] == "HOLD"
    assert manifest["local_verification_status"] == "UNVERIFIED_LOCAL"
    assert isinstance(manifest["components"], list)
    assert manifest["components"], "manifest must define at least one component"

    names = []
    for component in manifest["components"]:
        assert REQUIRED_COMPONENT_FIELDS <= component.keys()
        assert isinstance(component["file_name"], str) and component["file_name"]
        assert isinstance(component["expected_size_bytes"], int)
        assert component["expected_size_bytes"] > 0
        assert re.fullmatch(r"[0-9a-f]{64}", component["expected_sha256"])
        assert component["local_verification_status"] == "UNVERIFIED_LOCAL"
        names.append(component["file_name"])

        component_path = MANIFEST_PATH.parent / component["file_name"]
        # Model binaries are optional in the preparation checkout. If present,
        # validate their actual bytes; never treat absent files as verified.
        if component_path.exists():
            assert component_path.is_file(), (
                f"{component['file_name']} exists but is not a regular file"
            )
            actual_size = component_path.stat().st_size
            assert actual_size == component["expected_size_bytes"], (
                f"Size mismatch for {component['file_name']}: "
                f"got {actual_size}, expected {component['expected_size_bytes']}"
            )
            actual_sha256 = hashlib.sha256(component_path.read_bytes()).hexdigest()
            assert actual_sha256 == component["expected_sha256"], (
                f"SHA-256 mismatch for {component['file_name']}: "
                f"got {actual_sha256}, expected {component['expected_sha256']}"
            )

    assert len(names) == len(set(names)), "component file names must be unique"
