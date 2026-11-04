"""Regression tests for independent API GT and v0.3 signature/temporal checks."""
from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

V03 = Path(__file__).resolve().parents[1] / "experiments" / "the-hunt" / "v0.3"
sys.path.insert(0, str(V03))

import api_ground_truth as API_GT  # noqa: E402
import signature_checker as SIGNATURE  # noqa: E402
import temporal_contract as TEMPORAL  # noqa: E402


def make_wheel(files: dict[str, str | bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


class IndependentMatrixTests(unittest.TestCase):
    def test_api_matrix_counts_confusion_and_excludes_both_unknown_states(self):
        api_rows = {
            "tn": {"sample_id": "tn", "api_status": "VALID"},
            "fp": {"sample_id": "fp", "api_status": "VALID"},
            "tp": {"sample_id": "tp", "api_status": "INVALID"},
            "fn": {"sample_id": "fn", "api_status": "INVALID"},
            "gt_unknown": {"sample_id": "gt_unknown", "api_status": "INCONCLUSIVE"},
            "checker_unknown": {"sample_id": "checker_unknown", "api_status": "VALID"},
        }
        results = [
            {"sample_id": "tn", "signature_api_gt": {"status": "EXISTS"}},
            {"sample_id": "fp", "signature_api_gt": {"status": "INVALID_SIGNATURE"}},
            {"sample_id": "tp", "signature_api_gt": {"status": "INVALID_SIGNATURE"}},
            {"sample_id": "fn", "signature_api_gt": {"status": "EXISTS"}},
            {"sample_id": "gt_unknown", "signature_api_gt": {"status": "EXISTS"}},
            {"sample_id": "checker_unknown", "signature_api_gt": {"status": "INCONCLUSIVE"}},
        ]
        matrix = API_GT.api_valid_matrix(api_rows, results)
        self.assertEqual(
            {key: matrix[key] for key in ("TP", "TN", "FP", "FN")},
            {"TP": 1, "TN": 1, "FP": 1, "FN": 1},
        )
        self.assertEqual(matrix["api_gt_inconclusive_excluded"], 1)
        self.assertEqual(matrix["checker_inconclusive"], 1)
        self.assertEqual(matrix["scored_count"], 4)
        self.assertEqual(
            matrix["checker_basis"],
            "HASH_VERIFIED_RECOVERY_WHEEL_AT_SNAPSHOT_PINNED_VERSION",
        )

    def test_package_matrix_uses_package_gt_and_provenance_not_jamp_verdict(self):
        truth = [
            {"sample_id": "tp", "pypi_exists": True},
            {"sample_id": "tn", "pypi_exists": False},
            {"sample_id": "fp", "pypi_exists": False},
            {"sample_id": "fn", "pypi_exists": True},
            {"sample_id": "unknown", "pypi_exists": True},
        ]
        results = [
            {"sample_id": "tp", "provenance": {"status": "TRUSTED"}},
            {"sample_id": "tn", "provenance": {"status": "NOT_FOUND"}},
            {"sample_id": "fp", "provenance": {"status": "SUSPICIOUS"}},
            {"sample_id": "fn", "provenance": {"status": "NOT_FOUND"}},
            {"sample_id": "unknown", "provenance": {"status": "INCONCLUSIVE"},
             "jamp_verdict": "CLEAN"},
        ]
        matrix = API_GT.package_exists_matrix(results, truth)
        self.assertEqual(
            {key: matrix[key] for key in ("TP", "TN", "FP", "FN")},
            {"TP": 1, "TN": 1, "FP": 1, "FN": 1},
        )
        self.assertEqual(matrix["inconclusive_count"], 1)

    def test_duplicate_evaluator_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate sample_id"):
            API_GT.api_valid_matrix(
                {"x": {"sample_id": "x", "api_status": "VALID"}},
                [
                    {"sample_id": "x", "signature_then": {"status": "EXISTS"}},
                    {"sample_id": "x", "signature_then": {"status": "EXISTS"}},
                ],
            )

    def test_unsupported_api_gt_schema_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported independent API"):
            API_GT.validate_api_ground_truth(
                {"schema_version": "invented"},
                {}, {}, {}, {}, {}
            )


class SignatureCheckerRegressionTests(unittest.TestCase):
    def test_distribution_import_aliases(self):
        cases = [
            ("beautifulsoup4", "from bs4 import BeautifulSoup\nBeautifulSoup('x')", "bs4"),
            ("opencv-python", "import cv2\ncv2.imread('x')", "cv2"),
            ("scikit-learn", "import sklearn\nsklearn.fit()", "sklearn"),
            ("Pillow", "from PIL import Image\nImage.open('x')", "PIL"),
            ("PyYAML", "import yaml\nyaml.safe_load('x')", "yaml"),
            ("python-dotenv", "from dotenv import load_dotenv\nload_dotenv()", "dotenv"),
        ]
        for distribution, code, expected in cases:
            with self.subTest(distribution=distribution):
                aliases, calls, unsupported = SIGNATURE._imports_and_calls(code, distribution)
                self.assertTrue(aliases)
                self.assertFalse(unsupported)
                self.assertEqual(calls[0]["module"], expected)

    def test_instantiated_pydantic_subclass_traces_to_base_model(self):
        code = (
            "from pydantic import BaseModel\n"
            "class User(BaseModel):\n"
            "    name: str\n"
            "User()\n"
        )
        aliases, calls, unsupported = SIGNATURE._imports_and_calls(code, "pydantic")
        self.assertIn("BaseModel", aliases)
        self.assertFalse(unsupported)
        self.assertEqual(calls, [{
            "module": "pydantic",
            "symbol_path": ["BaseModel"],
            "source_expression": "User",
            "operation": "inherited_constructor",
        }])
        result = SIGNATURE.inspect_wheel_bytes(
            make_wheel({"pydantic/__init__.py": "class BaseModel:\n    pass\n"}),
            calls,
        )
        self.assertEqual(result["status"], "EXISTS")

    def test_binary_extension_reached_through_star_import_is_inconclusive(self):
        wheel = make_wheel({
            "samplepkg/__init__.py": "from .facade import *\n",
            "samplepkg/facade.py": "from ._native import *\n",
            "samplepkg/_native.cpython-311-x86_64-linux-gnu.so": b"binary-placeholder",
        })
        _aliases, calls, unsupported = SIGNATURE._imports_and_calls(
            "import samplepkg\nsamplepkg.native_api()", "samplepkg"
        )
        result = SIGNATURE.inspect_wheel_bytes(wheel, calls, unsupported)
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["reason"], "binary_extension_not_inspected")

    def test_pydantic_dynamic_export_map_resolves_base_model(self):
        wheel = make_wheel({
            "pydantic/__init__.py": (
                "_dynamic_imports: dict = {'BaseModel': (__spec__.parent, '.main')}\n"
                "def __getattr__(name):\n"
                "    raise AttributeError(name)\n"
            ),
            "pydantic/main.py": "class BaseModel:\n    pass\n",
        })
        code = (
            "from pydantic import BaseModel\n"
            "class User(BaseModel):\n"
            "    name: str\n"
            "User()\n"
        )
        _aliases, calls, unsupported = SIGNATURE._imports_and_calls(code, "pydantic")
        result = SIGNATURE.inspect_wheel_bytes(wheel, calls, unsupported)
        self.assertEqual(result["status"], "EXISTS")

    def test_unrelated_binary_does_not_suppress_missing_symbol(self):
        wheel = make_wheel({
            "samplepkg/__init__.py": "def known_api():\n    return None\n",
            "samplepkg/_unrelated.cpython-311-x86_64-linux-gnu.so": b"binary-placeholder",
        })
        _aliases, calls, unsupported = SIGNATURE._imports_and_calls(
            "import samplepkg\nsamplepkg.missing_api()", "samplepkg"
        )
        result = SIGNATURE.inspect_wheel_bytes(wheel, calls, unsupported)
        self.assertEqual(result["status"], "INVALID_SIGNATURE")
        self.assertEqual(result["reason"], "symbol_missing")


class RecoveryWheelCheckerTests(unittest.TestCase):
    def test_recovery_wheel_requires_exact_snapshot_version_and_verified_bytes(self):
        wheel = make_wheel({
            "samplepkg/__init__.py": "def ok():\n    return True\n"
        })
        digest = hashlib.sha256(wheel).hexdigest()
        snapshot = {
            "sample_id": "hunt-v03-001",
            "package_name": "samplepkg",
            "pypi_version": "1.0",
            "resolution_status": "RESOLVED",
            "temporal_provenance": "PRE_GENERATION_REGISTRY_SNAPSHOT",
        }
        candidate = {
            "sample_id": "hunt-v03-001",
            "distribution": "samplepkg",
            "version": "1.0",
            "filename": "samplepkg-1.0-py3-none-any.whl",
            "relative_path": "hunt-v03-001/samplepkg-1.0-py3-none-any.whl",
            "size_bytes": len(wheel),
            "sha256": digest,
            "compatible_cpython311_linux_x86_64": True,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheelhouse = root / "wheelhouse" / "hunt-v03-001"
            wheelhouse.mkdir(parents=True)
            (wheelhouse / candidate["filename"]).write_bytes(wheel)
            result = TEMPORAL.check_signature_from_recovery(
                "import samplepkg\nsamplepkg.ok()",
                "samplepkg", snapshot, [candidate], root, "hunt-v03-001"
            )
            wrong_version = dict(candidate, version="2.0")
            mismatch = TEMPORAL.check_signature_from_recovery(
                "import samplepkg\nsamplepkg.ok()",
                "samplepkg", snapshot, [wrong_version], root, "hunt-v03-001"
            )
        self.assertEqual(result["status"], "EXISTS")
        self.assertEqual(result["checker_evidence_source"], "HASH_VERIFIED_RECOVERY_WHEELHOUSE")
        self.assertEqual(
            result["wheel_temporal_scope"],
            "RECOVERY_TIME_COMPATIBLE_WHEEL_AT_EXACT_SNAPSHOT_PINNED_VERSION; "
            "NOT_ORIGINAL_GENERATION_WHEEL_BUILD",
        )
        self.assertEqual(mismatch["status"], "INCONCLUSIVE")
        self.assertEqual(mismatch["reason"], "recovery_wheel_snapshot_version_mismatch")


class TemporalWheelCompatibilityTests(unittest.TestCase):
    def test_cpython311_linux_and_pure_python_wheels_are_accepted(self):
        self.assertTrue(TEMPORAL._wheel_compatible_with_cpython311_linux_x86_64(
            "pydantic-2.14.2-py3-none-any.whl"
        ))
        self.assertTrue(TEMPORAL._wheel_compatible_with_cpython311_linux_x86_64(
            "numpy-2.4.6-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
        ))

    def test_cpython315_windows_arm_wheel_is_rejected(self):
        self.assertFalse(TEMPORAL._wheel_compatible_with_cpython311_linux_x86_64(
            "numpy-2.5.4-cp315-cp315t-win_arm64.whl"
        ))

    def test_incompatible_temporal_wheel_is_inconclusive_before_inspection(self):
        wheel = make_wheel({"numpy/__init__.py": "def ok():\n    return True\n"})
        record = {
            "sample_id": "numpy-sample",
            "package_name": "numpy",
            "pypi_version": "2.5.4",
            "wheel_filename": "numpy-2.5.4-cp315-cp315t-win_arm64.whl",
            "wheel_sha256": hashlib.sha256(wheel).hexdigest(),
            "wheel_relative_path": "wheelhouse/numpy.whl",
            "resolution_status": "RESOLVED",
            "temporal_provenance": "PRE_GENERATION_REGISTRY_SNAPSHOT",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "wheelhouse").mkdir()
            (root / "wheelhouse" / "numpy.whl").write_bytes(wheel)
            result = TEMPORAL.check_signature_from_snapshot(
                "import numpy\nnumpy.ok()", "numpy", record, root
            )
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(
            result["reason"],
            "temporal_wheel_incompatible_with_cpython311_linux_x86_64",
        )


if __name__ == "__main__":
    unittest.main()
