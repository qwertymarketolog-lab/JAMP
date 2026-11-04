"""Contract tests for generation-time package and wheel evidence."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).parents[1] / "experiments/the-hunt/v0.3"
sys.path.insert(0, str(BASE))
import temporal_contract as TEMPORAL  # noqa: E402

EVALUATOR_SPEC = importlib.util.spec_from_file_location(
    "hunt_v03_temporal_evaluator", BASE / "evaluate_v0.3.py"
)
assert EVALUATOR_SPEC is not None and EVALUATOR_SPEC.loader is not None
EVALUATOR = importlib.util.module_from_spec(EVALUATOR_SPEC)
sys.modules[EVALUATOR_SPEC.name] = EVALUATOR
EVALUATOR_SPEC.loader.exec_module(EVALUATOR)


def wheel_bytes(source: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("samplepkg/__init__.py", source)
    return output.getvalue()


class TemporalSnapshotTests(unittest.TestCase):
    def _metadata(self, wheel: bytes) -> dict:
        digest = hashlib.sha256(wheel).hexdigest()
        return {
            "releases": {
                "1.0": [{
                    "packagetype": "bdist_wheel",
                    "filename": "samplepkg-1.0-py3-none-any.whl",
                    "url": "https://files.pythonhosted.org/packages/samplepkg-1.0.whl",
                    "upload_time_iso_8601": "2025-01-01T00:00:00Z",
                    "digests": {"sha256": digest},
                }],
                "2.0": [{
                    "packagetype": "bdist_wheel",
                    "filename": "samplepkg-2.0-py3-none-any.whl",
                    "url": "https://files.pythonhosted.org/packages/samplepkg-2.0.whl",
                    "upload_time_iso_8601": "2026-01-01T00:00:00Z",
                    "digests": {"sha256": digest},
                }],
            }
        }

    def test_latest_release_is_pinned_from_pre_generation_metadata(self):
        wheel = wheel_bytes("def ok():\n    return True\n")
        with patch.object(TEMPORAL, "fetch_pypi_json", return_value=(200, self._metadata(wheel))):
            record = TEMPORAL.capture_pre_generation_release("samplepkg")
        self.assertEqual(record["pypi_version"], "2.0")
        self.assertEqual(record["resolution_status"], "PINNED_BEFORE_GENERATION")
        self.assertEqual(record["temporal_provenance"], "PRE_GENERATION_REGISTRY_SNAPSHOT")
        self.assertIsNotNone(record["metadata_observed_timestamp_utc"])

    def test_unavailable_pypi_is_unresolved_not_live_fallback(self):
        with patch.object(TEMPORAL, "fetch_pypi_json", return_value=(503, None)):
            record = TEMPORAL.capture_pre_generation_release("samplepkg")
        self.assertEqual(record["resolution_status"], "UNRESOLVED")
        self.assertEqual(record["temporal_provenance"], "UNRESOLVED")

    def test_wheel_hash_mismatch_fails_closed(self):
        wheel = wheel_bytes("def ok():\n    return True\n")
        record = {
            "package_name": "samplepkg",
            "pypi_version": "2.0",
            "wheel_filename": "samplepkg-2.0.whl",
            "wheel_sha256": "0" * 64,
            "wheel_url": "https://files.pythonhosted.org/packages/samplepkg-2.0.whl",
            "resolution_status": "PINNED_BEFORE_GENERATION",
            "temporal_provenance": "PRE_GENERATION_REGISTRY_SNAPSHOT",
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self, _limit):
                return wheel

        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(TEMPORAL, "urlopen", return_value=Response()):
                result = TEMPORAL.finalize_wheel_snapshot(
                    record, Path(temporary) / "wheelhouse", "sample-1"
                )
            self.assertEqual(result["resolution_status"], "UNRESOLVED")
            self.assertEqual(result["resolution_reason"], "wheel_sha256_mismatch")
            self.assertIsNone(result["wheel_relative_path"])

    def test_multiple_versions_keep_the_pre_generation_wheel_offline(self):
        wheel = wheel_bytes("def ok():\n    return True\n")
        record = {
            "sample_id": "sample-1",
            "package_name": "samplepkg",
            "pypi_version": "2.0",
            "wheel_filename": "samplepkg-2.0-py3-none-any.whl",
            "wheel_sha256": hashlib.sha256(wheel).hexdigest(),
            "wheel_sha256_observed": hashlib.sha256(wheel).hexdigest(),
            "wheel_relative_path": "wheelhouse/sample-1.whl",
            "resolution_status": "RESOLVED",
            "temporal_provenance": "PRE_GENERATION_REGISTRY_SNAPSHOT",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheelhouse = root / "wheelhouse"
            wheelhouse.mkdir()
            (wheelhouse / "sample-1.whl").write_bytes(wheel)
            with (
                patch.object(TEMPORAL, "fetch_pypi_json", side_effect=AssertionError("network used")),
                patch.object(TEMPORAL, "urlopen", side_effect=AssertionError("network used")),
            ):
                result = TEMPORAL.check_signature_from_snapshot(
                    "import samplepkg\nsamplepkg.ok()",
                    "samplepkg",
                    record,
                    root,
                )
            self.assertEqual(result["status"], "EXISTS")
            self.assertEqual(result["pypi_version"], "2.0")
            self.assertEqual(result["temporal_provenance"], "PRE_GENERATION_REGISTRY_SNAPSHOT")

    def test_missing_wheel_and_tampered_wheel_are_inconclusive(self):
        record = {
            "sample_id": "sample-1",
            "package_name": "samplepkg",
            "pypi_version": "2.0",
            "wheel_sha256": "0" * 64,
            "wheel_relative_path": "wheelhouse/missing.whl",
            "resolution_status": "RESOLVED",
            "temporal_provenance": "PRE_GENERATION_REGISTRY_SNAPSHOT",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = TEMPORAL.check_signature_from_snapshot(
                "import samplepkg\nsamplepkg.ok()", "samplepkg", record, root
            )
            self.assertEqual(missing["reason"], "temporal_wheel_missing")
            wheelhouse = root / "wheelhouse"
            wheelhouse.mkdir()
            (wheelhouse / "missing.whl").write_bytes(b"tampered")
            mismatch = TEMPORAL.check_signature_from_snapshot(
                "import samplepkg\nsamplepkg.ok()", "samplepkg", record, root
            )
            self.assertEqual(mismatch["reason"], "temporal_wheel_sha256_mismatch")

    def test_uninstalled_package_is_not_mislabeled_as_generation_environment(self):
        environment = {
            "captured_at_utc": "2026-11-04T00:00:00Z",
            "installed_distributions": [],
        }
        self.assertEqual(environment["installed_distributions"], [])
        record = {
            "package_name": "samplepkg",
            "temporal_provenance": "PRE_GENERATION_REGISTRY_SNAPSHOT",
        }
        self.assertNotEqual(record["temporal_provenance"], "GENERATION_ENVIRONMENT")

    def test_snapshot_timestamp_and_manifest_hash_are_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "generation_snapshot.json"
            digest = TEMPORAL.write_generation_snapshot(
                path,
                generation_timestamp_utc="2026-11-04T06:00:00Z",
                provider_name="anymodel",
                requested_model_id="ds/deepseek-v4-pro",
                provider_model_id="ds/deepseek-v4-pro",
                generation_environment={"installed_distributions": []},
                packages=[],
            )
            snapshot = TEMPORAL.load_generation_snapshot(path)
            self.assertEqual(snapshot["generation_timestamp_utc"], "2026-11-04T06:00:00Z")
            self.assertEqual(snapshot["snapshot_sha256"], digest)
            snapshot["generation_timestamp_utc"] = "2026-11-05T06:00:00Z"
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                TEMPORAL.load_generation_snapshot(path)

    def test_evaluator_keeps_api_valid_now_and_then_separate(self):
        wheel = wheel_bytes("def ok():\n    return True\n")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheelhouse = root / "wheelhouse"
            wheelhouse.mkdir()
            (wheelhouse / "sample-0.whl").write_bytes(wheel)
            package_record = {
                "sample_id": "sample-0",
                "package_name": "samplepkg",
                "pypi_version": "2.0",
                "wheel_filename": "samplepkg-2.0-py3-none-any.whl",
                "wheel_sha256": hashlib.sha256(wheel).hexdigest(),
                "wheel_relative_path": "wheelhouse/sample-0.whl",
                "resolution_status": "RESOLVED",
                "temporal_provenance": "PRE_GENERATION_REGISTRY_SNAPSHOT",
            }
            snapshot_path = root / "generation_snapshot.json"
            snapshot_hash = TEMPORAL.write_generation_snapshot(
                snapshot_path,
                generation_timestamp_utc="2026-11-04T06:00:00Z",
                provider_name="anymodel",
                requested_model_id="test/model",
                provider_model_id="test/model",
                generation_environment={"installed_distributions": []},
                packages=[package_record],
            )
            response_rows = []
            truth_rows = []
            for index in range(100):
                sample_id = f"sample-{index}"
                response_rows.append({
                    "sample_id": sample_id,
                    "package_name": "samplepkg",
                    "prompt": f"prompt-{index}",
                    "request_status": "SUCCESS" if index == 0 else "ABSTAINED",
                    "code": "import samplepkg\nsamplepkg.ok()" if index == 0 else "",
                })
                truth_rows.append({
                    "sample_id": sample_id,
                    "package_name": "samplepkg",
                    "prompt": f"prompt-{index}",
                    "ground_truth": "CLEAN",
                    "pypi_exists": True,
                })
            response_path = root / "responses.json"
            response_bytes = (
                json.dumps({"samples": response_rows}, indent=2, sort_keys=True) + "\n"
            ).encode()
            response_path.write_bytes(response_bytes)
            prompt_hash = "a" * 64
            truth_path = root / "ground_truth.json"
            truth_path.write_text(json.dumps({
                "prompt_dataset_sha256": prompt_hash,
                "samples": truth_rows,
            }), encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps({
                "llm_responses_sha256": hashlib.sha256(response_bytes).hexdigest(),
                "prompt_dataset_sha256": prompt_hash,
                "provider_name": "anymodel",
                "temperature": 0.7,
                "requested_model_id": "test/model",
                "request_count": 100,
                "successful_requests": 1,
                "abstained_requests": 99,
                "failed_requests": 0,
                "generation_snapshot_sha256": snapshot_hash,
            }), encoding="utf-8")
            with (
                patch.object(EVALUATOR, "check_provenance", return_value={"status": "TRUSTED"}),
                patch.object(
                    EVALUATOR,
                    "check_signature",
                    return_value={"status": "INVALID_SIGNATURE", "reason": "live-current-wheel"},
                ),
            ):
                report = EVALUATOR.evaluate(
                    response_path, root / "result.json", manifest_path, truth_path, snapshot_path
                )
            result = next(row for row in report["results"] if row["sample_id"] == "sample-0")
            self.assertFalse(result["api_valid_now"])
            self.assertTrue(result["api_valid_then"])
            self.assertEqual(result["temporal_evidence_status"], "PRE_GENERATION_REGISTRY_SNAPSHOT")
            self.assertEqual(result["jamp_verdict"], "CLEAN")
            self.assertEqual(report["api_valid_now_counts"]["invalid"], 1)
            self.assertEqual(report["api_valid_then_counts"]["valid"], 1)
    def test_post_generation_only_record_cannot_claim_valid_then(self):
        record = {
            "package_name": "samplepkg",
            "resolution_status": "RESOLVED",
            "temporal_provenance": "POST_GENERATION_RESOLUTION",
        }
        with tempfile.TemporaryDirectory() as temporary:
            result = TEMPORAL.check_signature_from_snapshot(
                "import samplepkg\nsamplepkg.ok()", "samplepkg", record, Path(temporary)
            )
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["reason"], "TEMPORAL_EVIDENCE_MISSING")


if __name__ == "__main__":
    unittest.main()
