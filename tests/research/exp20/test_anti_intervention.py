"""Static anti-intervention checks for EXP-20 telemetry."""

from pathlib import Path


def test_exp20_telemetry_contains_no_intervention_calls() -> None:
    source = Path(__file__).with_name("conftest.py").read_text(encoding="utf-8")
    forbidden = (
        "gc." + "collect(",
        "gc." + "disable(",
        "gc." + "enable(",
        "monkeypatch",
        "pytest." + "runtestloop",
    )
    assert not any(token in source for token in forbidden)


def test_exp20_telemetry_is_research_only() -> None:
    repo_root = Path(__file__).parents[3]
    assert not (repo_root / "src" / "jamp" / "run.py").is_symlink()
