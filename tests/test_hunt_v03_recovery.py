"""Focused tests for immutable Hunt v0.3 artifact recovery."""
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
        prompts, responses, truths = [], [], []
        for index in range(100):
            sample_id = f"sample-{index:03d}"
            package = f"pkg-{index:03d}"
            prompt = f"check {package}"
            prompts.append({"sample_id": sample_id, "package_name": package, "prompt": prompt})
            status = "SUCCESS" if index < 18 else "ABSTAINED" if index < 99 else "FAILED"
            response = {
                "sample_id": sample_id,
                "package_name": package,
                "prompt": prompt,
                "request_status": status,
            }
            if status == "SUCCESS":
                response["code"] = f"import package_{index}\npackage_{index}.api()"
            elif status == "ABSTAINED":
                response["code"] = ""
            responses.append(response)
            exists = index < 20
            truths.append({
                "sample_id": sample_id,
                "package_name": package,
                "prompt": prompt,
                "ground_truth": "CLEAN" if exists else "HALLUCINATION",
                "pypi_exists": exists,
            })
        prompt_bytes = (json.dumps({"samples": prompts}, sort_keys=True) + "\n").encode()
        response_bytes = (json.dumps({"samples": responses}, sort_keys=True) + "\n").encode()
        truth_payload = {
            "prompt_dataset_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "label_scope": "distribution existence only; API correctness is not ground truth",
            "samples": truths,
        }
        truth_bytes = (json.dumps(truth_payload, sort_keys=True) + "\n").encode()
        manifest = {
            "provider_name": "anymodel",
            "requested_model_id": "am/nemotron-3-ultra-550b-a55b",
            "provider_model_id": "am/nemotron-3-ultra-550b-a55b",
            "evaluation_mode": "LIVE_LLM_PYPI_PACKAGE_EXISTENCE_ONLY",
            "request_count": 100,
            "successful_requests": 18,
            "abstained_requests": 81,
            "failed_requests": 1,
            "llm_responses_sha256": hashlib.sha256(response_bytes).hexdigest(),
            "prompt_dataset_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        }
        (root / "prompts.json").write_bytes(prompt_bytes)
        (root / "llm_responses_v3.json").write_bytes(response_bytes)
        (root / "ground_truth_v3.json").write_bytes(truth_bytes)
        (root / "generation_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_ast_probe_extraction_does_not_execute_candidate(self):
        code = (
            "import requests as rq\nfrom celery import Celery\n"
            "rq.get('https://example.com')\nCelery('x')"
        )
        probes = RECOVERY.extract_api_probes(code)
        self.assertIn({"module": "requests", "attributes": [], "callable": False}, probes)
        self.assertIn({"module": "requests", "attributes": ["get"], "callable": True}, probes)
        self.assertIn({"module": "celery", "attributes": ["Celery"], "callable": True}, probes)

    def test_candidate_code_is_never_executed_during_probe_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "executed.txt"
            code = (
                "import requests\n"
                f"open({str(marker)!r}, 'w').write('executed')\n"
                "requests.get('https://example.com')"
            )
            RECOVERY.extract_api_probes(code)
            self.assertFalse(marker.exists())

    def test_invalid_python_is_not_mislabeled_as_missing_api(self):
        with self.assertRaises(SyntaxError):
            RECOVERY.extract_api_probes("import requests\nif:")

    def test_runtime_probe_checks_real_symbol_and_missing_module(self):
        valid = RECOVERY.run_api_probe([{
            "module": "json",
            "attributes": ["dumps"],
            "callable": True,
        }])
        invalid = RECOVERY.run_api_probe([{
            "module": "jamp_missing_module_for_recovery_test",
            "attributes": [],
            "callable": False,
        }])
        self.assertIs(valid["api_valid"], True)
        self.assertIs(invalid["api_valid"], False)

    def test_requirements_reject_unsafe_distribution_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._source_fixture(root)
            path = root / "ground_truth_v3.json"
            payload = json.loads(path.read_text())
            payload["samples"][0]["package_name"] = "--index-url=https://evil.invalid"
            payload["samples"][0]["prompt"] = "check --index-url=https://evil.invalid"
            path.write_text(json.dumps(payload), encoding="utf-8")
            prompts_path = root / "prompts.json"
            prompts = json.loads(prompts_path.read_text())
            prompts["samples"][0]["package_name"] = "--index-url=https://evil.invalid"
            prompts["samples"][0]["prompt"] = "check --index-url=https://evil.invalid"
            prompt_bytes = (json.dumps(prompts, sort_keys=True) + "\n").encode()
            prompts_path.write_bytes(prompt_bytes)
            payload["prompt_dataset_sha256"] = hashlib.sha256(prompt_bytes).hexdigest()
            path.write_text(json.dumps(payload), encoding="utf-8")
            manifest_path = root / "generation_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["prompt_dataset_sha256"] = hashlib.sha256(prompt_bytes).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            responses_path = root / "llm_responses_v3.json"
            responses = json.loads(responses_path.read_text())
            responses["samples"][0]["package_name"] = "--index-url=https://evil.invalid"
            responses["samples"][0]["prompt"] = "check --index-url=https://evil.invalid"
            response_bytes = (json.dumps(responses, sort_keys=True) + "\n").encode()
            responses_path.write_bytes(response_bytes)
            manifest["llm_responses_sha256"] = hashlib.sha256(response_bytes).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsafe or invalid distribution name"):
                RECOVERY.prepare_requirements(
                    root, root / "requirements.txt", strict_hashes=False
                )

    def test_source_identity_and_status_counts_are_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._source_fixture(root)
            validated = RECOVERY.validate_source_artifact(root, strict_hashes=False)
            self.assertEqual(
                validated["status_counts"],
                {"SUCCESS": 18, "ABSTAINED": 81, "FAILED": 1},
            )
            self.assertEqual(len(validated["truth_by_id"]), 100)

    def test_recovery_preserves_two_axes_and_unknown_non_success_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "original"
            wheelhouse = base / "wheelhouse"
            output = base / "output"
            root.mkdir()
            wheelhouse.mkdir()
            self._source_fixture(root)
            (wheelhouse / "example-1.0-py3-none-any.whl").write_bytes(b"fixture-wheel")
            wheel_manifest = RECOVERY.build_wheel_manifest(wheelhouse, base / "wheel_manifest.json")
            self.assertEqual(wheel_manifest["wheel_count"], 1)
            report = RECOVERY.evaluate(
                root, wheelhouse, base / "wheel_manifest.json", output,
                probe_runner=lambda _probes: {"api_valid": True, "reason": "fixture"},
                strict_hashes=False,
            )
            self.assertEqual(report["attempted_sample_count"], 100)
            self.assertEqual(report["api_probe_eligible_count"], 18)
            self.assertEqual(report["qualification"], "NOT_GRANTED")
            rows = json.loads((output / "results_v0.3.json").read_text())["results"]
            self.assertEqual(sum(row["api_valid"] is True for row in rows), 18)
            self.assertTrue(all(row["api_valid"] is None for row in rows[18:]))
            self.assertTrue(all("package_exists" in row and "api_valid" in row for row in rows))


if __name__ == "__main__":
    unittest.main()
