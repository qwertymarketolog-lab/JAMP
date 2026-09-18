from pathlib import Path


def test_exp18_reference_code_isolated_from_core():
    root = Path(__file__).resolve().parents[3]
    source = root / "research" / "exp18" / "atomic_observation.py"

    text = source.read_text(encoding="utf-8")

    assert "from jamp" not in text
    assert "import jamp" not in text
    assert "from src.jamp" not in text
    assert "import src.jamp" not in text


def test_exp18_tests_are_under_research_namespace():
    path = Path(__file__).resolve()

    assert path.parts[-4:] == (
        "tests",
        "research",
        "exp18",
        "test_atomic_observation_isolation.py",
    )
