"""Tests for the independent Hunt wheel Ground Truth harness."""
from __future__ import annotations

import importlib.util
import io
import zipfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experiments" / "the-hunt" / "v0.3"
sys.path.insert(0, str(BASE))
import signature_checker as SIGNATURE_CHECKER

SPEC = importlib.util.spec_from_file_location(
    "hunt_ground_truth_harness", BASE / "ground_truth_harness.py"
)
assert SPEC is not None and SPEC.loader is not None
HARNESS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HARNESS
SPEC.loader.exec_module(HARNESS)


class GroundTruthHarnessContractTests(unittest.TestCase):
    def test_twelve_diagnostic_cases_have_unique_ids(self):
        case_ids = [case["case_id"] for case in HARNESS.CASE_DEFINITIONS]
        self.assertEqual(len(case_ids), 12)
        self.assertEqual(len(set(case_ids)), 12)

    def test_runtime_expectations_are_not_prelabelled(self):
        for case in HARNESS.CASE_DEFINITIONS:
            self.assertNotIn("expected_api_valid", case)
            self.assertNotIn("ground_truth", case)

    def test_api_valid_preserves_false_and_unknown(self):
        self.assertIs(HARNESS._probe_api_valid({"api_valid": True}), True)
        self.assertIs(HARNESS._probe_api_valid({"api_valid": False}), False)
        self.assertIsNone(HARNESS._probe_api_valid({"api_valid": None}))
        self.assertIsNone(HARNESS._probe_api_valid({"api_valid": "false"}))
        self.assertIsNone(HARNESS._probe_api_valid(None))

    def test_static_status_maps_only_definitive_results(self):
        self.assertIs(HARNESS._static_api_valid("EXISTS"), True)
        self.assertIs(HARNESS._static_api_valid("INVALID_SIGNATURE"), False)
        self.assertIsNone(HARNESS._static_api_valid("INCONCLUSIVE"))
        self.assertIsNone(HARNESS._static_api_valid("NOT_APPLICABLE"))

    def test_unknown_and_inconclusive_cases_are_excluded_from_confusion_matrix(self):
        rows = [
            {"api_valid": True, "static_api_valid": True},
            {"api_valid": False, "static_api_valid": False},
            {"api_valid": False, "static_api_valid": True},
            {"api_valid": True, "static_api_valid": False},
            {"api_valid": None, "static_api_valid": True},
            {
                "api_valid": True,
                "static_api_valid": None,
                "static_result": {"status": "INCONCLUSIVE"},
            },
            {
                "api_valid": True,
                "static_api_valid": None,
                "static_result": {"status": "NOT_APPLICABLE"},
            },
        ]
        result = HARNESS._metrics(rows)
        self.assertEqual(
            (result["tp"], result["fp"], result["tn"], result["fn"]),
            (1, 1, 1, 1),
        )
        self.assertEqual(result["resolved_case_count"], 4)
        self.assertEqual(result["total_case_count"], 7)
        self.assertAlmostEqual(result["coverage"], 4 / 7)
        self.assertEqual(result["ground_truth_unknown_count"], 1)
        self.assertEqual(result["static_inconclusive_count"], 1)
        self.assertEqual(result["static_not_applicable_count"], 1)
        self.assertEqual(result["static_unknown_count"], 2)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 0.5)

    def test_metrics_do_not_claim_precision_without_positive_predictions(self):
        result = HARNESS._metrics([
            {"api_valid": False, "static_api_valid": False},
            {"api_valid": False, "static_api_valid": None},
        ])
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["recall"])
        self.assertEqual(result["resolved_case_count"], 1)

    def test_target_metadata_rejects_a_version_or_hash_substitution(self):
        manifest = {
            "targets": {
                package: dict(pin) for package, pin in HARNESS.TARGETS.items()
            }
        }
        HARNESS._validate_target_metadata(manifest)
        manifest["targets"]["celery"]["version"] = "5.7.0rc1"
        with self.assertRaisesRegex(ValueError, "version mismatch"):
            HARNESS._validate_target_metadata(manifest)




class StaticWheelExportResolutionTests(unittest.TestCase):
    @staticmethod
    def _wheel(files: dict[str, str]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for path, source in files.items():
                archive.writestr(path, source)
        return buffer.getvalue()

    def test_httpx_style_star_imports_resolve_package_exports(self):
        wheel = self._wheel({
            "httpx/__init__.py": (
                "from ._api import *\n"
                "from ._client import *\n"
                "__all__ = ['get', 'Client']\n"
            ),
            "httpx/_api.py": "__all__ = ['get']\ndef get(): pass\n",
            "httpx/_client.py": "__all__ = ['Client']\nclass Client: pass\n",
        })
        result = SIGNATURE_CHECKER.inspect_wheel_bytes(
            wheel,
            [
                {"module": "httpx", "symbol_path": ["get"]},
                {"module": "httpx", "symbol_path": ["Client"]},
            ],
        )
        self.assertEqual(result["status"], "EXISTS")
        self.assertEqual(result["unresolved_calls"], [])

    def test_celery_style_recreate_module_resolves_lazy_exports(self):
        wheel = self._wheel({
            "celery/__init__.py": (
                "from . import local\n"
                "__all__ = ('Celery', 'shared_task')\n"
                "old_module, new_module = local.recreate_module(\n"
                "    __name__, by_module={\n"
                "        'celery.app': ['Celery', 'shared_task'],\n"
                "    }\n"
                ")\n"
            ),
            "celery/local.py": (
                "class LazyModule:\n"
                "    def __getattr__(self, name): return getattr(self, name)\n"
                "def recreate_module(*args, **kwargs): pass\n"
            ),
            "celery/app/__init__.py": "from .base import Celery, shared_task\n",
            "celery/app/base.py": (
                "class Celery: pass\n"
                "def shared_task(): pass\n"
            ),
        })
        result = SIGNATURE_CHECKER.inspect_wheel_bytes(
            wheel,
            [
                {"module": "celery", "symbol_path": ["Celery"]},
                {"module": "celery", "symbol_path": ["shared_task"]},
                {"module": "celery", "symbol_path": ["missing_symbol"]},
            ],
        )
        self.assertEqual(result["status"], "INVALID_SIGNATURE")
        self.assertEqual(
            [call["symbol_path"] for call in result["unresolved_calls"]],
            [["missing_symbol"]],
        )

    def test_dynamic_star_import_contract_is_inconclusive(self):
        wheel = self._wheel({
            "sample/__init__.py": "from .api import *\n",
            "sample/api.py": (
                "__all__ = build_exports()\n"
                "def present(): pass\n"
            ),
        })
        result = SIGNATURE_CHECKER.inspect_wheel_bytes(
            wheel, [{"module": "sample", "symbol_path": ["present"]}]
        )
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["reason"], "dynamic_attribute_present")

    def test_star_import_probe_checks_literal_all_membership(self):
        wheel = self._wheel({
            "sample/__init__.py": "__all__ = ['present']\n",
            "sample/api.py": "__all__ = ['present']\ndef present(): pass\n",
        })
        present = SIGNATURE_CHECKER.inspect_wheel_bytes(
            wheel,
            [{
                "operation": "star_import",
                "module": "sample",
                "symbol_path": ["present"],
            }],
        )
        missing = SIGNATURE_CHECKER.inspect_wheel_bytes(
            wheel,
            [{
                "operation": "star_import",
                "module": "sample",
                "symbol_path": ["not_exported"],
            }],
        )
        self.assertEqual(present["status"], "EXISTS")
        self.assertEqual(missing["status"], "INVALID_SIGNATURE")



if __name__ == "__main__":
    unittest.main()
