from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src" / "jamp"

FORBIDDEN_ROOTS = {
    "react",
    "vite",
    "frontend",
    "visual_merchant_hub",
}


def _module_root(name: str) -> str:
    return name.split(".", 1)[0].split("/", 1)[0]


def test_jamp_core_has_no_commercial_or_frontend_imports() -> None:
    violations: list[str] = []
    for path in CORE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if _module_root(name) in FORBIDDEN_ROOTS:
                    violations.append(f"{path.relative_to(ROOT)} -> {name}")
    assert not violations, "JAMP core imports forbidden commercial/boundary modules:\n" + "\n".join(violations)
