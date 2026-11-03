"""Contract tests for The Hunt v0.3 pipeline and fail-closed boundaries."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experiments" / "the-hunt" / "v0.3"
sys.path.insert(0, str(BASE))


def load_script(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, BASE / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


PROVENANCE = load_script("provenance_checker.py", "hunt_v03_provenance")
SIGNATURE = load_script("signature_checker.py", "hunt_v03_signature")
EVALUATOR = load_script("evaluate_v0.3.py", "hunt_v03_evaluator")
VERIFY_GT = load_script("verify_gt_v3.py", "hunt_v03_verify_gt")
RUN_LLM = load_script("run_llm_v3.py", "hunt_v03_run_llm")


def metadata(age_days: int, project_urls=None, author="Maintainer"):
    now = datetime(2026, 11, 3, tzinfo=UTC)
    first = now - timedelta(days=age_days)
    return now, {
        "info": {
            "project_urls": project_urls or {"Source": "https://github.com/example/pkg"},
            "author": author,
            "author_email": "",
        },
        "releases": {"1.0": [{"upload_time_iso_8601": first.isoformat()}]},
    }


def wheel_bytes(source: str, extra_files=None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("samplepkg/__init__.py", source)
        for name, content in (extra_files or {}).items():
            archive.writestr(name, content)
    return output.getvalue()


class ProvenanceScoringTests(unittest.TestCase):
    def test_age_penalty_boundaries_are_exclusive(self):
        expected = {29: (50, 50), 30: (20, 80), 364: (20, 80), 365: (0, 100)}
        for age, (penalty, score) in expected.items():
            with self.subTest(age_days=age):
                now, payload = metadata(age)
                result = PROVENANCE._score_metadata("samplepkg", payload, now)
                self.assertEqual(result["evidence"]["age_penalty"], penalty)
                self.assertEqual(result["trust_score"], score)

    def test_missing_release_dates_is_inconclusive(self):
        result = PROVENANCE._score_metadata(
            "samplepkg",
            {"info": {"author": "A", "project_urls": {}}, "releases": {"1.0": []}},
        )
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["reason"], "missing_dates")
        self.assertTrue(result["evidence"]["pypi_exists"])

    def test_homepage_does_not_count_as_repository(self):
        now, payload = metadata(365, {"Homepage": "https://example.com"})
        result = PROVENANCE._score_metadata("samplepkg", payload, now)
        self.assertFalse(result["evidence"]["repository_present"])
        self.assertEqual(result["evidence"]["repository_penalty"], 30)
        self.assertEqual(result["trust_score"], 70)

    def test_github_and_gitlab_project_urls_count_as_repositories(self):
        for host in ("github.com", "gitlab.com"):
            with self.subTest(host=host):
                now, payload = metadata(365, {"Source": f"https://{host}/example/pkg"})
                result = PROVENANCE._score_metadata("samplepkg", payload, now)
                self.assertTrue(result["evidence"]["repository_present"])
                self.assertEqual(result["trust_score"], 100)

    def test_lookalike_repository_hostname_does_not_count(self):
        now, payload = metadata(
            365, {"Source": "https://github.com.attacker.invalid/example/pkg"}
        )
        result = PROVENANCE._score_metadata("samplepkg", payload, now)
        self.assertFalse(result["evidence"]["repository_present"])

    def test_http_404_is_not_found(self):
        with patch.object(PROVENANCE, "fetch_pypi_json", return_value=(404, None)):
            self.assertEqual(PROVENANCE.check_provenance("missing-pkg")["status"], "NOT_FOUND")


class SignatureSafetyTests(unittest.TestCase):
    def _check(self, source_code: str, generated_code: str):
        archive_bytes = wheel_bytes(source_code)
        payload = {
            "releases": {
                "1.0": [
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "samplepkg-1.0-py3-none-any.whl",
                        "url": "https://files.pythonhosted.org/samplepkg.whl",
                        "upload_time_iso_8601": "2026-11-03T00:00:00Z",
                        "digests": {"sha256": hashlib.sha256(archive_bytes).hexdigest()},
                    }
                ]
            }
        }
        with (
            patch.object(SIGNATURE, "fetch_pypi_json", return_value=(200, payload)),
            patch.object(SIGNATURE, "_download_wheel", return_value=archive_bytes),
        ):
            return SIGNATURE.check_signature(generated_code, "samplepkg")

    def test_existing_method_is_found_and_wheel_hash_is_recorded(self):
        result = self._check(
            "def get_secure_data():\n    return None\n",
            "import samplepkg\nsamplepkg.get_secure_data()",
        )
        self.assertEqual(result["status"], "EXISTS")
        self.assertEqual(
            result["wheel_sha256_expected"], result["wheel_sha256_observed"]
        )

    def test_missing_method_is_invalid_signature(self):
        result = self._check(
            "def known_method():\n    return None\n",
            "import samplepkg\nsamplepkg.get_secure_data()",
        )
        self.assertEqual(result["status"], "INVALID_SIGNATURE")

    def test_dynamic_call_receiver_is_inconclusive(self):
        result = self._check(
            "class Client:\n    pass\n",
            "import samplepkg\nsamplepkg.Client().missing_method()",
        )
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["reason"], "dynamic_call_receiver_unresolved")

    def test_hash_mismatch_is_inconclusive(self):
        payload = {
            "releases": {
                "1.0": [
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "samplepkg.whl",
                        "url": "https://files.pythonhosted.org/samplepkg.whl",
                        "upload_time": "2026-11-03T00:00:00Z",
                        "digests": {"sha256": "0" * 64},
                    }
                ]
            }
        }
        with (
            patch.object(SIGNATURE, "fetch_pypi_json", return_value=(200, payload)),
            patch.object(SIGNATURE, "_download_wheel", return_value=b"not-the-wheel"),
        ):
            result = SIGNATURE.check_signature(
                "import samplepkg\nsamplepkg.run()", "samplepkg"
            )
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["reason"], "hash_mismatch")

    def test_missing_wheel_hash_is_inconclusive(self):
        payload = {
            "releases": {
                "1.0": [
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "samplepkg.whl",
                        "url": "https://files.pythonhosted.org/samplepkg.whl",
                        "upload_time": "2026-11-03T00:00:00Z",
                    }
                ]
            }
        }
        with patch.object(SIGNATURE, "fetch_pypi_json", return_value=(200, payload)):
            result = SIGNATURE.check_signature(
                "import samplepkg\nsamplepkg.run()", "samplepkg"
            )
        self.assertEqual(result["reason"], "wheel_hash_missing")

    def test_invalid_generated_python_is_inconclusive(self):
        result = SIGNATURE.check_signature("import samplepkg\nsamplepkg.(", "samplepkg")
        self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_traversal_member_is_ignored_without_disk_write(self):
        archive_bytes = wheel_bytes(
            "def safe_method():\n    return None\n",
            {"../../evil.py": "raise RuntimeError('must never execute')\n"},
        )
        result = SIGNATURE.inspect_wheel_bytes(
            archive_bytes, [{"module": "samplepkg", "symbol_path": ["safe_method"]}]
        )
        self.assertEqual(result["status"], "EXISTS")
        self.assertNotIn("../../evil.py", result["inspected_source_paths"])
        self.assertIsNone(SIGNATURE._safe_member_path("../../evil.py"))

    def test_wheel_is_never_extracted_to_disk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            SIGNATURE.read_wheel_sources(wheel_bytes("def safe_method():\n    return None\n"))
            self.assertEqual(list(root.iterdir()), [])


class EvaluatorDecisionTests(unittest.TestCase):
    def test_baseline_ast_and_pypi_decision_order(self):
        self.assertEqual(EVALUATOR._baseline_verdict("def (", True), "SYNTAX_ERROR")
        self.assertEqual(
            EVALUATOR._baseline_verdict("x = 1", False), "PACKAGE_NOT_FOUND"
        )
        self.assertEqual(EVALUATOR._baseline_verdict("x = 1", True), "NO_IMPORTS")
        self.assertEqual(EVALUATOR._baseline_verdict("import samplepkg", True), "CLEAN")

    def test_not_found_is_caught_even_without_a_wheel(self):
        self.assertEqual(
            EVALUATOR._jamp_verdict(
                {"status": "NOT_FOUND"},
                {"status": "INCONCLUSIVE", "reason": "wheel_not_found"},
            ),
            "HALLUCINATION_CAUGHT",
        )

    def test_inconclusive_is_not_counted_as_success(self):
        self.assertEqual(
            EVALUATOR._jamp_verdict(
                {"status": "INCONCLUSIVE"}, {"status": "EXISTS"}
            ),
            "INCONCLUSIVE",
        )

    def test_exact_mcnemar_known_values(self):
        self.assertEqual(EVALUATOR.exact_mcnemar(0, 0), 1.0)
        self.assertEqual(EVALUATOR.exact_mcnemar(2, 0), 0.5)

    def test_prompt_generator_is_exactly_100_and_stable(self):
        first = VERIFY_GT.build_prompts()
        second = VERIFY_GT.build_prompts()
        self.assertEqual(len(first), 100)
        self.assertEqual(first, second)
        self.assertEqual(len({item["sample_id"] for item in first}), 100)

    def test_groq_request_sends_experiment_temperature(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return json.dumps(
                    {
                        "id": "req-test",
                        "model": "test-model",
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '{"package_name":"pkg","code":"import pkg"}'
                                    ),
                                },
                            },
                        ],
                    }
                ).encode("utf-8")

        with patch.object(RUN_LLM, "urlopen", return_value=FakeResponse()) as opener:
            result, error = RUN_LLM._call_groq(
                api_key="test-secret",
                endpoint="https://api.groq.com/openai/v1/chat/completions",
                model_id="test-model",
                prompt="test prompt",
                max_tokens=128,
            )
        self.assertIsNone(error)
        self.assertIsNotNone(result)
        request = opener.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["temperature"], 0.7)
        self.assertEqual(body["model"], "test-model")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")


if __name__ == "__main__":
    unittest.main()
