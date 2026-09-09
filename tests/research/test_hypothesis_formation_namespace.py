"""P22.8 namespace-isolation diagnostic contract.

This temporary harness imports the dedicated P22.8 namespace directly so the
legacy P20.5 ``jamp.research.hypothesis`` module cannot mask collection.
"""
from __future__ import annotations

import ast
import inspect

from jamp.research import hypothesis_formation as hypothesis


def test_p22_8_target_namespace_is_imported_directly():
    assert hypothesis is not None


def test_p22_8_public_boundary_is_declared():
    assert hypothesis.__all__ == (
        "Hypothesis", "HypothesisSet", "build_hypothesis_set",
        "verify_hypothesis_provenance",
    )


def test_p22_8_production_module_has_not_been_implemented_at_red():
    assert hypothesis.Hypothesis


def test_target_module_source_is_inspectable():
    source = inspect.getsource(hypothesis)
    assert source


def test_target_module_has_no_legacy_lifecycle_symbols():
    source = inspect.getsource(hypothesis)
    assert "HypothesisStatus" not in source
    assert "transition_hypothesis" not in source


def test_target_module_has_no_environment_imports():
    tree = ast.parse(inspect.getsource(hypothesis))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert not imports.intersection({"os", "pathlib", "socket", "urllib", "requests", "httpx"})


def test_target_module_has_no_runtime_environment_names():
    tree = ast.parse(inspect.getsource(hypothesis))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names.intersection({"time", "random", "id", "environ"})


def test_target_module_has_no_decision_logic_names():
    forbidden = {
        "select", "select_node", "select_nodes", "rank", "sort", "sorted",
        "filter", "threshold", "heuristic", "estimate", "approximate",
        "goal", "objective", "utility", "fitness", "probability", "prediction",
        "confidence", "weight", "score", "relevance", "priority", "optimize",
        "optimization", "bayesian",
    }
    tree = ast.parse(inspect.getsource(hypothesis))
    names = {node.id.lower() for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr.lower() for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not (names | attrs).intersection(forbidden)
