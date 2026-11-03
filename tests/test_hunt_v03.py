"""Contract tests for The Hunt v0.3 provenance and static signature checks."""
from __future__ import annotations

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


def metadata(age_days: int, project_urls=None, author="Maintainer"):
    now = datetime(2026, 11, 3, tzinfo=UTC)
    first = now - timedelta(days=age_days)
    return now, {
        "info": {
            "project_urls": project_urls or {"Source": "https://github.com/example/pkg"},
            "author": author,
            "author_email": "",
        },
        "releases": {
            "1.0": [{"upload_time_iso_8601": first.isoformat()}],
        },
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
        now, payload = metadata(365, {"Source": "https://github.com.attacker.invalid/example/pkg"})
        result = PROVENANCE._score_metadata("samplepkg", payload, now)
        self.assertFalse(result["evidence"]["repository_present"])

    def test_http_404_is_not_found(self):
        with patch.object(PROVENANCE, "fetch_pypi_json", return_value=(404, None)):
            self.assertEqual(PROVENANCE.check_provenance("missing-pkg")["status"], "NOT_FOUND")


class SignatureSafetyTests(unittest.TestCase):
    def _check(self, source_code: str, generated_code: str):
        payload = {
            "urls": [
                {
                    "packagetype": "bdist_wheel",
                    "filename": "samplepkg-1.0-py3-none-any.whl",
                    "url": "https://files.pythonhosted.org/samplepkg.whl",
                    "upload_time": "2026-11-03T00:00:00Z",
                }
            ]
        }
        with (
            patch.object(SIGNATURE, "fetch_pypi_json", return_value=(200, payload)),
            patch.object(SIGNATURE, "_download_wheel", return_value=wheel_bytes(source_code)),
        ):
            return SIGNATURE.check_signature(generated_code, "samplepkg")

    def test_existing_method_is_found(self):
        result = self._check(
            "def get_secure_data():\n    return None\n",
            "import samplepkg\nsamplepkg.get_secure_data()",
        )
        self.assertEqual(result["status"], "EXISTS")

    def test_missing_method_is_invalid_signature(self):
        result = self._check(
            "def known_method():\n    return None\n",
            "import samplepkg\nsamplepkg.get_secure_data()",
        )
        self.assertEqual(result["status"], "INVALID_SIGNATURE")

    def test_invalid_generated_python_is_inconclusive(self):
        result = SIGNATURE.check_signature("import samplepkg\nsamplepkg.(", "samplepkg")
        self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_traversal_member_is_ignored_without_disk_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_bytes = wheel_bytes(
                "def safe_method():\n    return None\n",
                {"../../evil.py": "raise RuntimeError('must never execute')\n"},
            )
            result = SIGNATURE.inspect_wheel_bytes(
                archive_bytes,
                [{"module": "samplepkg", "symbol_path": ["safe_method"]}],
            )
            self.assertEqual(result["status"], "EXISTS")
            self.assertNotIn("../../evil.py", result["inspected_source_paths"])
            self.assertIsNone(SIGNATURE._safe_member_path("../../evil.py"))
            self.assertFalse((root.parent / "evil.py").exists())
            self.assertFalse((root / "evil.py").exists())

    def test_wheel_is_never_extracted_to_disk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_bytes = wheel_bytes("def safe_method():\n    return None\n")
            SIGNATURE.read_wheel_sources(archive_bytes)
            self.assertEqual(list(root.iterdir()), [])


class EvaluatorDecisionTests(unittest.TestCase):
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
                {"status": "INCONCLUSIVE"},
                {"status": "EXISTS"},
            ),
            "INCONCLUSIVE",
        )

    def test_exact_mcnemar_no_discordance(self):
        self.assertEqual(EVALUATOR.exact_mcnemar(0, 0), 1.0)

    def test_evaluator_writes_results_file(self):
        sample = {
            "sample_id": "case-1",
            "package_name": "samplepkg",
            "prompt": "Use the samplepkg run API.",
            "code": "import samplepkg\nsamplepkg.run()",
            "ground_truth": "CLEAN",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "samples.json"
            output = root / "results_v0.3.json"
            source.write_text(json.dumps({"samples": [sample]}), encoding="utf-8")
            with (
                patch.object(
                    EVALUATOR,
                    "check_provenance",
                    return_value={"status": "TRUSTED", "evidence": {"pypi_exists": True}},
                ),
                patch.object(EVALUATOR, "check_signature", return_value={"status": "EXISTS"}),
            ):
                report = EVALUATOR.evaluate(source, output)
            self.assertTrue(output.is_file())
            self.assertEqual(report["jamp"]["accuracy"], 1.0)
            self.assertEqual(report["paired_scored_count"], 1)


if __name__ == "__main__":
    unittest.main()
