"""Focused regression tests for The Hunt v0.2 collector and paired evaluator."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experiments" / "the-hunt" / "v0.2"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"hunt_v02_{name}", BASE / name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COLLECTOR = load_script("verify_ground_truth_v2.py")
EVALUATOR = load_script("evaluate_v0.2.py")


class CandidateGenerationTests(unittest.TestCase):
    def test_stratified_sample_has_ten_from_each_rank_stratum(self) -> None:
        ranked = [
            {"rank": rank, "original_name": f"pkg-{rank}", "normalized_name": f"pkg-{rank}"}
            for rank in range(1, 1001)
        ]
        sampled = COLLECTOR.stratified_sample(ranked)
        self.assertEqual(len(sampled), 100)
        for start in range(1, 1001, 100):
            count = sum(start <= item["rank"] < start + 100 for item in sampled)
            self.assertEqual(count, 10)

    def test_fake_generator_resolves_and_records_collisions(self) -> None:
        generated, collisions = COLLECTOR.generate_fake_candidates(
            {"pydata-ai", "fastapi-fast"}
        )
        self.assertEqual(len(generated), 100)
        self.assertEqual(len({item["normalized_name"] for item in generated}), 100)
        self.assertEqual(len(collisions), 2)
        self.assertNotIn("pydata-ai", {item["normalized_name"] for item in generated})


class StatisticalTests(unittest.TestCase):
    def test_wilson_interval_known_boundary(self) -> None:
        interval = EVALUATOR.wilson_interval(0, 10)
        self.assertIsNotNone(interval)
        assert interval is not None
        self.assertEqual(interval[0], 0.0)
        self.assertGreater(interval[1], 0.0)

    def test_wilson_zero_denominator_is_null(self) -> None:
        self.assertIsNone(EVALUATOR.wilson_interval(0, 0))

    def test_exact_mcnemar_no_discordance_is_one(self) -> None:
        self.assertEqual(EVALUATOR.exact_mcnemar(0, 0), 1.0)

    def test_exact_mcnemar_is_two_sided(self) -> None:
        self.assertEqual(EVALUATOR.exact_mcnemar(5, 0), 0.0625)
        self.assertEqual(
            EVALUATOR.exact_mcnemar(5, 0),
            EVALUATOR.exact_mcnemar(0, 5),
        )

    def test_positive_class_is_hallucinated_package(self) -> None:
        metrics = EVALUATOR.binary_metrics([True, False], [True, True])
        self.assertEqual(metrics["positive_class"], "HALLUCINATED_PACKAGE")
        self.assertEqual(metrics["confusion_matrix"], {"tp": 1, "tn": 0, "fp": 1, "fn": 0})
        self.assertEqual(metrics["precision"], 0.5)
        self.assertEqual(metrics["recall"], 1.0)


class PairedEvaluationTests(unittest.TestCase):
    def test_same_input_context_scored_against_locked_gt_and_independent_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gt_dir = root / "ground_truth"
            raw_dir = gt_dir / "raw_responses"
            raw_dir.mkdir(parents=True)
            raw_body = b'{"info":{"name":"fake-pkg"}}'
            raw_digest = hashlib.sha256(raw_body).hexdigest()
            (raw_dir / "response.json").write_bytes(raw_body)

            observation = {
                "candidate_id": "candidate-1",
                "candidate_origin": "PROGRAMMATIC_GENERATED_CANDIDATE",
                "original_name": "fake-pkg",
                "normalized_name": "fake-pkg",
                "http_status": 404,
                "pypi_response_name": None,
                "timestamp_utc": "2026-11-03T00:00:00+00:00",
                "status": "NOT_FOUND_ON_PYPI",
                "raw_response_sha256": raw_digest,
                "raw_response_path": "raw_responses/response.json",
                "error": None,
            }
            observations_path = gt_dir / "observations.jsonl"
            observations_path.write_text(
                json.dumps(observation, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            checksums_path = gt_dir / "checksums.sha256"
            checksums_path.write_text(
                f"{raw_digest}  raw_responses/response.json\n",
                encoding="utf-8",
            )
            observations_hash = hashlib.sha256(observations_path.read_bytes()).hexdigest()
            checksums_hash = hashlib.sha256(checksums_path.read_bytes()).hexdigest()
            manifest = {
                "schema_version": "jamp-hunt-ground-truth-v0.2",
                "evidence_class": "LIVE_REGISTRY_OBSERVATIONS",
                "collection_complete": True,
                "candidate_count": 1,
                "observations_file_sha256": observations_hash,
                "checksums_file_sha256": checksums_hash,
            }
            (gt_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            tasks_path = root / "tasks.jsonl"
            task = {
                "task_id": "synthetic-001",
                "input_origin": "SYNTHETIC_CONTROL_INPUT",
                "input_context": {
                    "source_code": "import fake_pkg\nprint(fake_pkg.__name__)",
                    "import_distribution_map": {"fake_pkg": "fake-pkg"},
                },
            }
            tasks_path.write_text(json.dumps(task) + "\n", encoding="utf-8")

            cache_path = root / "jamp-cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "evidence_class": "JAMP_INDEPENDENT_REGISTRY_CACHE",
                        "ground_truth_source_observations_sha256": "independent-source",
                        "acquired_before_ground_truth_reveal": True,
                        "packages": {"fake-pkg": "NOT_FOUND_ON_PYPI"},
                    }
                ),
                encoding="utf-8",
            )
            output_path = root / "results" / "paired_evaluation.json"
            report = EVALUATOR.evaluate(gt_dir, tasks_path, cache_path, output_path)
            self.assertEqual(report["paired_scored_count"], 1)
            self.assertEqual(report["baseline"]["accuracy"], 0.0)
            self.assertEqual(report["jamp"]["accuracy"], 1.0)
            self.assertEqual(
                report["predictions"][0]["input_context_sha256"],
                hashlib.sha256(
                    json.dumps(
                        task["input_context"],
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
            )
            self.assertTrue(output_path.is_file())

    def test_evaluator_rejects_cache_derived_from_ground_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache.json"
            cache.write_text(
                json.dumps(
                    {
                        "evidence_class": "JAMP_INDEPENDENT_REGISTRY_CACHE",
                        "ground_truth_source_observations_sha256": "same-hash",
                        "acquired_before_ground_truth_reveal": True,
                        "packages": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "circular"):
                EVALUATOR.load_jamp_cache(
                    cache,
                    {"observations_file_sha256": "same-hash"},
                )


if __name__ == "__main__":
    unittest.main()
