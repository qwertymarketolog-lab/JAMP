from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FROZEN_RUN_PY_SHA256 = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"


def test_frozen_core_run_py_unchanged() -> None:
    run_py = ROOT / "src" / "jamp" / "run.py"
    assert hashlib.sha256(run_py.read_bytes()).hexdigest() == FROZEN_RUN_PY_SHA256


def test_exp20_contains_only_research_harness_files() -> None:
    exp20 = ROOT / "tests" / "research" / "exp20"
    allowed = {"__init__.py", "fixtures_text.py", "text_adapter.py", "test_isolation.py", "test_text_adapter.py"}
    assert {p.name for p in exp20.iterdir()} == allowed
