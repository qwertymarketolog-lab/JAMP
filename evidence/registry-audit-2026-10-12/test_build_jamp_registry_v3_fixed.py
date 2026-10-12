import csv
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

SPEC = importlib.util.spec_from_file_location("registry", "build_jamp_registry_v3_fixed.py")
registry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(registry)

SHA = "a" * 40

class RegistryFailClosedTests(unittest.TestCase):
    def test_paginated_ci_count_must_match(self):
        pages = [{"total_count": 2, "workflow_runs": [{"id": 1}, {"id": 2}]}]
        merged = registry._merge_pages(pages, "actions/runs")
        self.assertEqual(merged["total_count"], 2)
        with self.assertRaises(registry.GhApiError):
            registry._merge_pages([{"total_count": 3, "workflow_runs": [{"id": 1}]}], "actions/runs")

    def test_paginated_ci_counts_must_agree(self):
        with self.assertRaises(registry.GhApiError):
            registry._merge_pages([
                {"total_count": 2, "workflow_runs": [{"id": 1}]},
                {"total_count": 3, "workflow_runs": [{"id": 2}]},
            ], "actions/runs")

    @patch.object(registry.subprocess, "run")
    def test_single_json_decode_error_is_handled(self, mock_run):
        mock_run.return_value = Mock(stdout="{broken", stderr="", returncode=0)
        payload, error = registry.run_gh_api_single("repos/example")
        self.assertIsNone(payload)
        self.assertIn("Expecting property name", error)

    @patch.object(registry.subprocess, "run")
    def test_permission_error_is_handled(self, mock_run):
        mock_run.side_effect = PermissionError("Permission denied for gh")
        payload, error = registry.run_gh_api_single("repos/example")
        self.assertIsNone(payload)
        self.assertIn("Permission denied for gh", error)

    @patch.object(registry.subprocess, "run")
    def test_paginated_permission_error_is_handled(self, mock_run):
        mock_run.side_effect = PermissionError("Permission denied for gh")
        payload, error = registry.run_gh_api("repos/example?per_page=100")
        self.assertIsNone(payload)
        self.assertIn("Permission denied for gh", error)

    def test_empty_branch_inventory_is_rejected(self):
        valid_ci = {"total_count": 0, "workflow_runs": []}
        ok, errors = registry._validate_inventory(SHA, [], [], valid_ci)
        self.assertFalse(ok)
        self.assertTrue(any("Branch inventory is empty" in e for e in errors))

    def test_main_sha_race_is_rejected(self):
        branches = [{"name": "main", "commit": {"sha": "b" * 40}}]
        ok, errors = registry._validate_inventory(SHA, branches, [], {"total_count": 0, "workflow_runs": []})
        self.assertFalse(ok)
        self.assertTrue(any("changed between baseline" in e for e in errors))

    def test_frozen_core_unknown_differs_from_mismatch(self):
        self.assertNotEqual("UNKNOWN / HOLD", "MISMATCH / HOLD")

    def test_atomic_csv_replace_failure_preserves_original_and_cleans_temp(self):
        records = [{
            "branch": "main",
            "sha": SHA,
            "pr_info": "N/A",
            "pr_state": "N/A",
            "ci_info": "No CI runs for exact SHA",
            "recommendation": "KEEP",
            "reason": "Protected main branch baseline",
        }]
        fieldnames = ["branch", "sha", "pr_info", "pr_state", "ci_info", "recommendation", "reason"]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "registry.csv"
            original_bytes = b"existing-registry-must-remain\\n"
            output_path.write_bytes(original_bytes)

            with patch.object(registry.os, "replace", side_effect=OSError("simulated replace failure")):
                with self.assertRaisesRegex(OSError, "simulated replace failure"):
                    registry._write_csv_atomically(records, output_path, fieldnames)

            self.assertEqual(output_path.read_bytes(), original_bytes)
            self.assertEqual(list(Path(temp_dir).iterdir()), [output_path])

    def test_atomic_csv_write(self):
        records = [{
            "branch": "main",
            "sha": SHA,
            "pr_info": "N/A",
            "pr_state": "N/A",
            "ci_info": "No CI runs for exact SHA",
            "recommendation": "KEEP",
            "reason": "Protected main branch baseline",
        }]
        fieldnames = ["branch", "sha", "pr_info", "pr_state", "ci_info", "recommendation", "reason"]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "registry.csv"
            registry._write_csv_atomically(records, output_path, fieldnames)

            self.assertTrue(output_path.is_file())
            with output_path.open("r", newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["branch"], "main")
            self.assertEqual(rows[0]["sha"], SHA)
            self.assertEqual(rows[0]["recommendation"], "KEEP")
            self.assertEqual(list(Path(temp_dir).iterdir()), [output_path])


    @patch.object(registry, "run_gh_api_single")
    @patch.object(registry, "run_gh_api")
    def test_full_audit_fail_closed_on_bad_inventory(self, mock_run_gh_api, mock_run_gh_api_single):
        mock_run_gh_api_single.side_effect = [
            ({"commit": {"sha": SHA}}, None),
            ({"sha": registry.EXPECTED_FROZEN_SHA}, None),
        ]
        mock_run_gh_api.side_effect = [
            ([], None),
            ([], None),
            ({"workflow_runs": []}, None),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / registry.CSV_FILENAME
            output_path.write_text("existing-registry-must-remain\\n", encoding="utf-8")
            with patch.object(registry, "CSV_FILENAME", str(output_path)):
                result = registry.execute_controlled_audit()

            self.assertFalse(result["inventory_complete"])
            self.assertTrue(any("Branch inventory is empty" in e for e in result["errors"]))
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                "existing-registry-must-remain\\n",
            )
            self.assertEqual(mock_run_gh_api.call_count, 3)
            self.assertEqual(mock_run_gh_api_single.call_count, 2)


    @patch.object(registry, "run_gh_api_single")
    @patch.object(registry, "run_gh_api")
    def test_full_audit_fail_closed_on_main_sha_mismatch(
        self, mock_run_gh_api, mock_run_gh_api_single
    ):
        mock_run_gh_api_single.side_effect = [
            ({"commit": {"sha": SHA}}, None),
            ({"sha": registry.EXPECTED_FROZEN_SHA}, None),
        ]
        mock_run_gh_api.side_effect = [
            ([{"name": "main", "commit": {"sha": "b" * 40}}], None),
            ([], None),
            ({"workflow_runs": []}, None),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / registry.CSV_FILENAME
            original_content = "existing-registry-must-remain\\n"
            output_path.write_text(original_content, encoding="utf-8")

            with patch.object(registry, "CSV_FILENAME", str(output_path)):
                result = registry.execute_controlled_audit()

            self.assertFalse(result["inventory_complete"])
            self.assertEqual(result["frozen_core_delta"], 0)
            self.assertTrue(
                any("changed between baseline" in error for error in result["errors"])
            )
            self.assertEqual(output_path.read_text(encoding="utf-8"), original_content)
            self.assertEqual(list(Path(temp_dir).iterdir()), [output_path])
            self.assertEqual(mock_run_gh_api.call_count, 3)
            self.assertEqual(mock_run_gh_api_single.call_count, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
