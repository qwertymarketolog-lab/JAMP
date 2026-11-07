"""Focused tests for immutable DeepSeek v0.3 recovery contract."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "experiments/the-hunt/v0.3/recover_v03.py"
SPEC = importlib.util.spec_from_file_location("recover_v03", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
RECOVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECOVERY)


class RecoveryTests(unittest.TestCase):
    def _source_fixture(self, root: Path) -> None:
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir()
        prompts, responses, truths, packages = [], [], [], []
        for index in range(100):
            sample_id = f"hunt-v03-{index + 1:03d}"
            package = f"pkg-{index + 1:03d}"
            prompt = f"check {package}"
            prompts.append({"sample_id": sample_id, "package_name": package, "prompt": prompt})
            status = "SUCCESS" if index < 21 else "ABSTAINED" if index < 98 else "MALFORMED_RESPONSE"
            code = "import json\njson.dumps({})" if status == "SUCCESS" else ""
            responses.append({"sample_id": sample_id, "package_name": package,
                              "prompt": prompt, "request_status": status, "code": code})
            exists = index < 20
            truths.append({"sample_id": sample_id, "package_name": package, "prompt": prompt,
                           "ground_truth": "CLEAN" if exists else "HALLUCINATION",
                           "pypi_exists": exists})
            if index < 20:
                filename = f"pkg_{index + 1:03d}-1.0-py3-none-any.whl"
                archive_name = f"fixturehash-{filename}"
                relative = f"wheelhouse/{archive_name}"
                wheel = wheelhouse / archive_name
                wheel.write_bytes(f"fixture-wheel-{index}".encode())
                digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
                packages.append({"sample_id": sample_id, "package_name": package,
                                 "pypi_version": "1.0", "resolution_status": "RESOLVED",
                                 "wheel_filename": filename, "wheel_relative_path": relative,
                                 "wheel_sha256": digest, "wheel_sha256_observed": digest})
            else:
                packages.append({"sample_id": sample_id, "package_name": package,
                                 "pypi_version": None, "resolution_status": "UNRESOLVED",
                                 "wheel_filename": None, "wheel_relative_path": None,
                                 "wheel_sha256": None, "wheel_sha256_observed": None})
        prompt_bytes = (json.dumps({"samples": prompts}, sort_keys=True) + "\n").encode()
        response_bytes = (json.dumps({"samples": responses}, sort_keys=True) + "\n").encode()
        truth_bytes = (json.dumps({
            "prompt_dataset_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "label_scope": "distribution existence only; API correctness is not ground truth",
            "samples": truths,
        }, sort_keys=True) + "\n").encode()
        snapshot = {"schema_version": "fixture", "provider_name": "anymodel",
                    "requested_model_id": "ds/deepseek-v4-pro",
                    "provider_model_id": "ds/deepseek-v4-pro",
                    "generation_environment": {"python_implementation": "CPython",
                                               "python_version": "3.11.17",
                                               "platform": "Linux x86_64"},
                    "packages": packages}
        snapshot["snapshot_sha256"] = RECOVERY.canonical_json_hash(snapshot, "snapshot_sha256")
        snapshot_bytes = (json.dumps(snapshot, sort_keys=True) + "\n").encode()
        manifest = {"provider_name": "anymodel", "requested_model_id": "ds/deepseek-v4-pro",
                    "provider_model_id": "ds/deepseek-v4-pro",
                    "evaluation_mode": "LIVE_LLM_PYPI_PACKAGE_EXISTENCE_ONLY",
                    "generation_snapshot_file": "generation_snapshot.json",
                    "generation_snapshot_sha256": snapshot["snapshot_sha256"],
                    "generation_snapshot": {"captured_at_utc": "fixture"},
                    "request_count": 100, "successful_requests": 21,
                    "abstained_requests": 77, "failed_requests": 2,
                    "llm_responses_sha256": hashlib.sha256(response_bytes).hexdigest(),
                    "prompt_dataset_sha256": hashlib.sha256(prompt_bytes).hexdigest()}
        (root / "prompts.json").write_bytes(prompt_bytes)
        (root / "llm_responses_v3.json").write_bytes(response_bytes)
        (root / "ground_truth_v3.json").write_bytes(truth_bytes)
        (root / "generation_snapshot.json").write_bytes(snapshot_bytes)
        (root / "generation_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_source_snapshot_and_all_original_wheel_hashes_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._source_fixture(root)
            validated = RECOVERY.validate_source_artifact(root, strict_hashes=False)
            self.assertEqual(validated["status_counts"], RECOVERY.EXPECTED_STATUS_COUNTS)
            wheel = next((root / "wheelhouse").glob("*.whl"))
            wheel.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "wheel SHA-256 mismatch"):
                RECOVERY.validate_source_artifact(root, strict_hashes=False)

    def test_snapshot_digest_is_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._source_fixture(root)
            path = root / "generation_snapshot.json"
            snapshot = json.loads(path.read_text())
            snapshot["tamper_marker"] = "changed-without-rehash"
            path.write_text(json.dumps(snapshot))
            with self.assertRaisesRegex(ValueError, "canonical SHA-256 mismatch"):
                RECOVERY.validate_source_artifact(root, strict_hashes=False)

    def test_requirements_are_exact_snapshot_pins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._source_fixture(root)
            requirements, pins = root / "requirements.txt", root / "pins.json"
            rows = RECOVERY.prepare_requirements(root, requirements, pins, strict_hashes=False)
            self.assertEqual(len(rows), 20)
            self.assertTrue(all(row["requirement"].endswith("==1.0") for row in rows))
            self.assertNotIn(">=", requirements.read_text())
            self.assertEqual(len(json.loads(pins.read_text())["pins"]), 20)

    def test_dynamic_import_without_static_target_is_inconclusive(self):
        code = """import importlib
name = get_name()
importlib.import_module(name)
__import__(resolve_module_name())
"""
        probes, unresolved = RECOVERY.analyze_code(code)
        self.assertTrue(probes)
        self.assertEqual(len(unresolved), 2)
        self.assertTrue(all(
            item["reason"] == "dynamic_import_target_not_static" for item in unresolved
        ))

    def test_constant_dynamic_import_is_resolved_statically(self):
        probes, unresolved = RECOVERY.analyze_code(
            "import importlib\nimportlib.import_module('json')"
        )
        self.assertFalse(unresolved)
        self.assertIn({"module": "json", "attributes": [], "callable": False}, probes)

    def test_wheel_manifest_rejects_source_distributions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wheelhouse = root / "wheelhouse"
            sample = wheelhouse / "s1"
            sample.mkdir(parents=True)
            (sample / "pkg-1.0.tar.gz").write_bytes(b"sdist")
            pins = {"pins": [{"sample_id": "s1", "package_name": "pkg",
                              "version": "1.0", "requirement": "pkg==1.0"}]}
            (root / "pins.json").write_text(json.dumps(pins))
            (root / "download.tsv").write_text("s1\\tSUCCESS\\n")
            with self.assertRaisesRegex(ValueError, "non-wheel"):
                RECOVERY.build_wheel_manifest(
                    wheelhouse, root / "pins.json", root / "download.tsv", root / "manifest.json"
                )

    def test_wheel_manifest_marks_missing_compatible_wheel_inconclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wheelhouse = root / "wheelhouse"
            wheelhouse.mkdir()
            pins = {"pins": [{"sample_id": "s1", "package_name": "pkg",
                              "version": "1.0", "requirement": "pkg==1.0"}]}
            (root / "pins.json").write_text(json.dumps(pins))
            (root / "download.tsv").write_text("s1\tFAILED\n")
            result = RECOVERY.build_wheel_manifest(
                wheelhouse, root / "pins.json", root / "download.tsv", root / "manifest.json"
            )
            self.assertEqual(result["samples"]["s1"]["status"], "INCONCLUSIVE")
            self.assertEqual(result["samples"]["s1"]["reason"], "wheel_download_failed")

    def test_static_dunder_import_target_is_resolved(self):
        probes, unresolved = RECOVERY.analyze_code("__import__('json')")
        self.assertFalse(unresolved)
        self.assertIn({"module": "json", "attributes": [], "callable": False}, probes)

    def test_missing_attribute_is_not_double_counted_as_not_callable(self):
        result = RECOVERY.run_api_probe([{
            "module": "json",
            "attributes": ["jamp_missing_symbol_for_recovery_test"],
            "callable": True,
        }])
        self.assertIs(result["api_valid"], False)
        self.assertEqual(len(result["missing"]), 1)
        self.assertEqual(result["missing"][0]["kind"], "missing_attribute_or_submodule")

    def test_probe_extraction_does_not_execute_candidate_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "executed"
            RECOVERY.extract_api_probes(
                f"open({str(marker)!r}, 'w').write('bad')\nimport json\njson.dumps({{}})"
            )
            self.assertFalse(marker.exists())

    def test_recovery_wheelhouse_hashes_are_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wheelhouse = root / "wheelhouse"
            folder = wheelhouse / "sample-1"
            folder.mkdir(parents=True)
            wheel = folder / "pkg-1.0-py3-none-any.whl"
            wheel.write_bytes(b"wheel-bytes")
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            record = {"relative_path": "sample-1/pkg-1.0-py3-none-any.whl",
                      "sha256": digest, "size_bytes": wheel.stat().st_size}
            manifest = {"wheels": [record],
                        "wheelhouse_sha256": hashlib.sha256(
                            json.dumps([record], sort_keys=True, separators=(",", ":")).encode()
                        ).hexdigest()}
            RECOVERY.verify_recovery_wheelhouse(wheelhouse, manifest)
            wheel.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                RECOVERY.verify_recovery_wheelhouse(wheelhouse, manifest)

    def test_generation_environment_must_be_cpython311_linux_x86_64(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._source_fixture(root)
            path = root / "generation_snapshot.json"
            snapshot = json.loads(path.read_text())
            snapshot["generation_environment"]["python_version"] = "3.15.0"
            snapshot["snapshot_sha256"] = RECOVERY.canonical_json_hash(
                snapshot, "snapshot_sha256"
            )
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            manifest_path = root / "generation_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["generation_snapshot_sha256"] = snapshot["snapshot_sha256"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not CPython 3.11 Linux x86_64"):
                RECOVERY.validate_source_artifact(root, strict_hashes=False)

    def test_source_status_contract_is_21_77_2(self):
        self.assertEqual(RECOVERY.EXPECTED_STATUS_COUNTS,
                         {"SUCCESS": 21, "ABSTAINED": 77, "MALFORMED_RESPONSE": 2})


if __name__ == "__main__":
    unittest.main()
