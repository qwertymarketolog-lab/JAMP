"""Focused regression tests for The Hunt v0.3.1 signature inspection."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "experiments" / "the-hunt" / "v0.3" / "signature_checker.py"
sys.path.insert(0, str(CHECKER_PATH.parent))
SPEC = importlib.util.spec_from_file_location("hunt_v031_signature_checker", CHECKER_PATH)
assert SPEC is not None and SPEC.loader is not None
SIGNATURE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SIGNATURE
SPEC.loader.exec_module(SIGNATURE)


def make_wheel(files: dict[str, str | bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def check_with_wheel(generated_code: str, wheel: bytes) -> dict:
    payload = {
        "releases": {
            "1.0": [
                {
                    "packagetype": "bdist_wheel",
                    "filename": "samplepkg-1.0-py3-none-any.whl",
                    "url": "https://files.pythonhosted.org/samplepkg.whl",
                    "upload_time_iso_8601": "2026-11-03T00:00:00Z",
                    "digests": {"sha256": hashlib.sha256(wheel).hexdigest()},
                }
            ]
        }
    }
    with (
        patch.object(SIGNATURE, "fetch_pypi_json", return_value=(200, payload)),
        patch.object(SIGNATURE, "_download_wheel", return_value=wheel),
    ):
        return SIGNATURE.check_signature(generated_code, "samplepkg")


def test_requests_style_reexport_resolves_to_exists() -> None:
    wheel = make_wheel(
        {
            "samplepkg/__init__.py": "from .api import get\n",
            "samplepkg/api.py": "def get(url):\n    return url\n",
        }
    )
    result = check_with_wheel("import samplepkg\nsamplepkg.get('/health')", wheel)
    assert result["status"] == "EXISTS"
    assert result["unresolved_calls"] == []


def test_binary_extension_makes_missing_python_symbol_inconclusive() -> None:
    wheel = make_wheel(
        {
            "samplepkg/__init__.py": "'''pure python facade'''\n",
            "samplepkg/_native.so": b"binary-placeholder",
        }
    )
    result = check_with_wheel("import samplepkg\nsamplepkg.native_call()", wheel)
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "binary_extension_not_inspected"


def test_module_getattr_makes_missing_symbol_inconclusive() -> None:
    wheel = make_wheel(
        {
            "samplepkg/__init__.py": (
                "def __getattr__(name):\n    raise AttributeError(name)\n"
            ),
        }
    )
    result = check_with_wheel("import samplepkg\nsamplepkg.dynamic_api()", wheel)
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "dynamic_attribute_present"


def test_pure_python_package_without_symbol_is_invalid_signature() -> None:
    wheel = make_wheel(
        {
            "samplepkg/__init__.py": "def known_api():\n    return None\n",
            "samplepkg/client.py": "class Client:\n    pass\n",
        }
    )
    result = check_with_wheel("import samplepkg\nsamplepkg.missing_api()", wheel)
    assert result["status"] == "INVALID_SIGNATURE"
    assert result["reason"] == "symbol_missing"


def test_dynamic_in_unrelated_module_is_invalid_signature() -> None:
    wheel = make_wheel(
        {
            "samplepkg/__init__.py": "",
            "samplepkg/api.py": "def known_api():\n    return None\n",
            "samplepkg/other.py": (
                "def __getattr__(name):\n    raise AttributeError(name)\n"
            ),
        }
    )
    result = check_with_wheel(
        "import samplepkg.api as target\ntarget.missing_api()", wheel
    )
    assert result["status"] == "INVALID_SIGNATURE"
    assert result["reason"] == "symbol_missing"


def test_dynamic_in_resolution_chain_is_inconclusive() -> None:
    wheel = make_wheel(
        {
            "samplepkg/__init__.py": "from .dynamic import lazy_api\n",
            "samplepkg/dynamic.py": (
                "def __getattr__(name):\n    raise AttributeError(name)\n"
            ),
        }
    )
    result = check_with_wheel(
        "import samplepkg\nsamplepkg.lazy_api()", wheel
    )
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "dynamic_attribute_present"


def test_clean_static_symbol_is_exists() -> None:
    wheel = make_wheel(
        {
            "samplepkg/__init__.py": "from .api import get\n",
            "samplepkg/api.py": "def get(url):\n    return url\n",
            "samplepkg/other.py": (
                "def __getattr__(name):\n    raise AttributeError(name)\n"
            ),
        }
    )
    result = check_with_wheel(
        "import samplepkg\nsamplepkg.get('/health')", wheel
    )
    assert result["status"] == "EXISTS"
