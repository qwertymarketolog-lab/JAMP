from __future__ import annotations

import ast
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / "tests" / "research" / "exp20"
FROZEN_RUN_PY_SHA = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"


def python_files():
    return sorted(RESEARCH.glob("*.py"))


def test_research_modules_do_not_import_jamp():
    for path in python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        ]
        imports += [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        assert all(name != "jamp" and not name.startswith("jamp.") for name in imports)


def test_frozen_core_run_py_blob_is_unchanged():
    run_py = ROOT / "src" / "jamp" / "run.py"
    actual = subprocess.check_output(["git", "hash-object", str(run_py)], text=True).strip()
    assert actual == FROZEN_RUN_PY_SHA


def test_exp20_contains_only_research_harness_files():
    allowed = {
        "__init__.py",
        "fixtures_text.py",
        "text_adapter.py",
        "test_isolation.py",
        "test_text_adapter.py",
    }
    actual = {
        path.name
        for path in RESEARCH.iterdir()
        if path.is_file()
    }
    assert actual == allowed
