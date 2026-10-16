"""Unit tests for attempt-aligned AnyModel availability comparison."""

import unittest

from scripts.research.compare_anymodel_availability_runs import (
    classify,
    median_latency,
    normalize,
)


class AnyModelComparisonTests(unittest.TestCase):
    def test_normalizes_run1_observations_by_attempt_number(self):
        data = {
            "results": [{
                "model": "provider/model-a",
                "observations": [
                    {
                        "attempt": 2,
                        "http_status": 503,
                        "elapsed_ms": 900,
                        "error": "HTTP 503",
                    },
                    {
                        "attempt": 1,
                        "http_status": 200,
                        "elapsed_ms": 1200,
                        "error": None,
                    },
                ],
            }]
        }
        normalized = normalize(data)
        self.assertEqual(set(normalized["provider/model-a"]), {1, 2})
        self.assertEqual(normalized["provider/model-a"][1]["status_code"], 200)
        self.assertEqual(normalized["provider/model-a"][2]["status_code"], 503)

    def test_normalizes_run2_transport_by_attempt_number(self):
        data = {
            "models": [{
                "model_id": "provider/model-a",
                "attempts": [
                    {
                        "attempt": 2,
                        "transport": {
                            "status_code": 503,
                            "timed_out": False,
                            "elapsed_ms": 900,
                        },
                    },
                    {
                        "attempt": 1,
                        "transport": {
                            "status_code": 200,
                            "timed_out": False,
                            "elapsed_ms": 1200,
                        },
                    },
                ],
            }]
        }
        normalized = normalize(data)
        self.assertEqual(normalized["provider/model-a"][1]["status_code"], 200)
        self.assertEqual(normalized["provider/model-a"][2]["status_code"], 503)

    def test_latency_does_not_change_status_classification(self):
        run1 = {
            1: {"status_code": 200, "timed_out": False, "elapsed_ms": 100, "error": None},
            2: {"status_code": 503, "timed_out": False, "elapsed_ms": 200, "error": "HTTP 503"},
        }
        run2 = {
            1: {"status_code": 200, "timed_out": False, "elapsed_ms": 9000, "error": None},
            2: {"status_code": 503, "timed_out": False, "elapsed_ms": 8000, "error": "HTTP 503"},
        }
        self.assertIn(
            "SAME_HTTP_OR_TIMEOUT_SIGNATURE_BY_ATTEMPT",
            classify(run1, run2),
        )
        self.assertEqual(median_latency(run1), 150)
        self.assertEqual(median_latency(run2), 8500)

    def test_detects_status_change_on_same_attempt(self):
        run1 = {
            1: {"status_code": 200, "timed_out": False, "elapsed_ms": 100, "error": None},
            2: {"status_code": 200, "timed_out": False, "elapsed_ms": 200, "error": None},
        }
        run2 = {
            1: {"status_code": 200, "timed_out": False, "elapsed_ms": 900, "error": None},
            2: {"status_code": 503, "timed_out": False, "elapsed_ms": 800, "error": "HTTP 503"},
        }
        self.assertIn(
            "HTTP_OR_TIMEOUT_SIGNATURE_CHANGED_BY_ATTEMPT",
            classify(run1, run2),
        )

    def test_detects_missing_attempt_and_duplicate_attempt(self):
        run1 = {
            "results": [{
                "model": "provider/model-a",
                "observations": [
                    {"attempt": 1, "http_status": 200},
                    {"attempt": 1, "http_status": 200},
                ],
            }]
        }
        with self.assertRaisesRegex(ValueError, "duplicate attempt number"):
            normalize(run1)

        different_sets = {
            1: {"status_code": 200, "timed_out": False},
            2: {"status_code": 200, "timed_out": False},
        }
        only_one = {
            1: {"status_code": 200, "timed_out": False},
        }
        self.assertIn("ATTEMPT_SET_CHANGED", classify(different_sets, only_one))


if __name__ == "__main__":
    unittest.main()
