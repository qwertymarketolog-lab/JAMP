"""Static contracts for post-merge main evidence workflows."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).parents[1] / ".github" / "workflows"


def _load_workflow(filename: str) -> dict[str, object]:
    payload = yaml.load(
        (WORKFLOWS / filename).read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert isinstance(payload, dict)
    return payload


def _job(workflow: dict[str, object], job_id: str) -> dict[str, object]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_id]
    assert isinstance(job, dict)
    return job


def _steps(job: dict[str, object]) -> list[dict[str, object]]:
    steps = job["steps"]
    assert isinstance(steps, list)
    return [step for step in steps if isinstance(step, dict)]


def _python_heredocs(job: dict[str, object]) -> list[str]:
    scripts = []
    pattern = re.compile(r"python\s+-\s+<<'PY'\n(.*?)\nPY", re.DOTALL)
    for step in _steps(job):
        run = step.get("run")
        if isinstance(run, str):
            scripts.extend(match.group(1) for match in pattern.finditer(run))
    return scripts


def test_main_research_loop_workflow_contract() -> None:
    workflow = _load_workflow("research-loop-v0-main.yml")
    assert workflow["name"] == "Research Loop v0 Gate (main)"
    assert workflow["on"] == {"push": {"branches": ["main"]}}

    job = _job(workflow, "research-loop-main")
    assert job["name"] == "Research Loop v0 Gate (main) /"
    scripts = _python_heredocs(job)
    assert len(scripts) == 1
    compile(scripts[0], "research-loop-v0-main.yml", "exec")

    artifacts = [
        step.get("with", {}).get("name")
        for step in _steps(job)
        if step.get("uses") == "actions/upload-artifact@v4"
        and isinstance(step.get("with"), dict)
    ]
    assert artifacts == ["research-loop-v0-main-evidence"]


def test_main_trusted_lineage_workflow_contract() -> None:
    workflow = _load_workflow("g1-trusted-lineage-main.yml")
    assert workflow["name"] == "G1 Trusted Lineage (main)"
    assert workflow["on"] == {"push": {"branches": ["main"]}}

    job = _job(workflow, "trusted-lineage-main")
    assert job["name"] == "G1 Trusted Lineage (main)"
    scripts = _python_heredocs(job)
    assert len(scripts) == 1
    compile(scripts[0], "g1-trusted-lineage-main.yml", "exec")

    artifacts = [
        step.get("with", {}).get("name")
        for step in _steps(job)
        if step.get("uses") == "actions/upload-artifact@v4"
        and isinstance(step.get("with"), dict)
    ]
    assert artifacts == ["g1-main-lineage-evidence"]


def test_g1_actions_run_job_url_regex_matches_numeric_ids() -> None:
    workflow = _load_workflow("g1-trusted-lineage-main.yml")
    scripts = _python_heredocs(_job(workflow, "trusted-lineage-main"))
    assert len(scripts) == 1

    tree = ast.parse(scripts[0])
    patterns = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "re"
        and node.func.attr == "search"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and "/actions/runs/" in node.args[0].value
    ]
    assert len(patterns) >= 4

    url = "https://github.com/qwertymarketolog-lab/JAMP/actions/runs/123456789/job/987654321"
    for pattern in patterns:
        match = re.search(pattern, url)
        assert match is not None
        assert match.groups() == ("123456789", "987654321")
