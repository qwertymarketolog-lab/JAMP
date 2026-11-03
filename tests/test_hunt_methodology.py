"""Regression tests for The Hunt ground-truth and paired scoring helpers."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "the-hunt" / "code-audit" / "verify_ground_truth.py"
SPEC = importlib.util.spec_from_file_location("hunt_verify_ground_truth", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


class GroundTruthTests(unittest.TestCase):
    def test_pypi_404_is_scoped_to_registry_absence(self) -> None:
        error = HTTPError("https://pypi.org/pypi/no-such/json", 404, "Not Found", None, None)
        with patch.object(VERIFY, "urlopen", side_effect=error):
            result = VERIFY.check_package("no-such")
        self.assertEqual(result["status"], "NOT_FOUND_ON_PYPI")
        self.assertEqual(result["http_status"], 404)

    def test_network_failure_is_inconclusive(self) -> None:
        with patch.object(VERIFY, "urlopen", side_effect=TimeoutError):
            result = VERIFY.check_package("network-unknown")
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIsNone(result["http_status"])

    def test_all_candidates_are_recorded_and_conflicts_are_not_fake(self) -> None:
        def observation(package: str, timeout: float = 5.0) -> dict[str, object]:
            exists = package in VERIFY.REAL_PACKAGES or package == "requests-extra"
            return {
                "candidate": package,
                "normalized_name": VERIFY.normalize_distribution_name(package),
                "status": "EXISTS_ON_PYPI" if exists else "NOT_FOUND_ON_PYPI",
                "http_status": 200 if exists else 404,
                "observed_at_utc": "2026-11-03T00:00:00+00:00",
                "source": "test://registry",
            }

        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(VERIFY, "check_package", side_effect=observation):
                report = VERIFY.verify_ground_truth(Path(temporary))
            self.assertEqual(report["candidate_count"], 30)
            self.assertIn("requests-extra", report["fake_candidate_conflicts"])
            self.assertNotIn("requests-extra", report["verified_fake_candidates"])
            saved = json.loads((Path(temporary) / "ground_truth.json").read_text())
            self.assertEqual(saved["schema_version"], "jamp-hunt-ground-truth-v1")
            valid_fakes = json.loads((Path(temporary) / "valid_fakes.json").read_text())
            self.assertNotIn("requests-extra", valid_fakes)


if __name__ == "__main__":
    unittest.main()
