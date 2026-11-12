"""Regression tests for the migrated static wheel signature checker."""
from __future__ import annotations

import hashlib
import io
import zipfile
from unittest.mock import patch

from jamp.server.checks import signature as SIGNATURE


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


def test_binary_extension_on_symbol_path_remains_inconclusive() -> None:
    wheel = make_wheel(
        {
            "samplepkg/__init__.py": "'''pure python facade'''\n",
            "samplepkg/_native.cpython-314-x86_64-linux-gnu.so": b"binary-placeholder",
        }
    )
    result = check_with_wheel(
        "import samplepkg\nsamplepkg._native.native_call()", wheel
    )
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "binary_extension_not_inspected"


def test_unrelated_binary_extension_does_not_block_missing_symbol() -> None:
    wheel = make_wheel(
        {
            "samplepkg/__init__.py": "def known_api():\n    return None\n",
            "samplepkg/_unrelated.cpython-314-x86_64-linux-gnu.so": b"binary-placeholder",
        }
    )
    result = check_with_wheel("import samplepkg\nsamplepkg.missing_api()", wheel)
    assert result["status"] == "INVALID_SIGNATURE"
    assert result["reason"] == "symbol_missing"


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


def test_parent_getattr_is_relevant_when_child_module_file_is_unbound() -> None:
    wheel = make_wheel(
        {
            "samplepkg/__init__.py": (
                "def __getattr__(name):\n"
                "    if name == 'api':\n"
                "        return DynamicAPI()\n"
                "    raise AttributeError(name)\n"
            ),
            "samplepkg/api.py": "def known_method():\n    return None\n",
        }
    )
    result = check_with_wheel(
        "import samplepkg\nsamplepkg.api.missing_method()", wheel
    )
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "dynamic_attribute_present"


def test_importfrom_binds_child_module_on_parent_package() -> None:
    wheel = make_wheel(
        {
            "samplepkg/__init__.py": (
                "def __getattr__(name):\n"
                "    if name == 'api':\n"
                "        return DynamicAPI()\n"
                "    raise AttributeError(name)\n"
                "from .api import known\n"
            ),
            "samplepkg/api.py": "def known():\n    return None\n",
        }
    )
    result = check_with_wheel(
        "import samplepkg\nsamplepkg.api.missing_method()", wheel
    )
    assert result["status"] == "INVALID_SIGNATURE"
    assert result["reason"] == "symbol_missing"
