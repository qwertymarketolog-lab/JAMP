from __future__ import annotations

from jamp.runtime import resolver as resolver_module
from jamp.runtime.resolver import PILOT_MODEL_ID, CapabilityResolver
from jamp.runtime.selector import ModelSelector


def _matrix(search_models=None, tool_models=None):
    return {
        "task_profiles": {
            "search_and_extraction": {
                "eligible_models": list(search_models or [f"matrix/search-{i}" for i in range(12)])
            },
            "tool_execution_agent": {
                "eligible_models": list(tool_models or [f"matrix/tool-{i}" for i in range(7)])
            },
            "long_context_analysis": {"eligible_models": []},
            "strict_compliance_safety": {
                "eligible_models": ["matrix/safety-1", "matrix/safety-2"]
            },
        }
    }


def test_search_profile_selects_direct_glm_from_versioned_pilot(monkeypatch):
    monkeypatch.setattr(resolver_module, "_load_derived_matrix", lambda: _matrix())
    eligible = CapabilityResolver().get_eligible_models("search_and_extraction")

    action, selected = ModelSelector().select_model(eligible, "search_and_extraction")

    assert action == "EXECUTE"
    assert selected == PILOT_MODEL_ID
    assert len(eligible) == 12


def test_glm_pilot_is_not_selected_for_other_task_profiles(monkeypatch):
    original_tool_models = [f"matrix/tool-{i}" for i in range(7)]
    monkeypatch.setattr(
        resolver_module,
        "_load_derived_matrix",
        lambda: _matrix(tool_models=original_tool_models),
    )
    eligible = CapabilityResolver().get_eligible_models("tool_execution_agent")

    action, selected = ModelSelector().select_model(eligible, "tool_execution_agent")

    assert action == "EXECUTE"
    assert tuple(eligible) == tuple(original_tool_models)
    assert selected != PILOT_MODEL_ID
    pilot = resolver_module._load_pilot_models()["models"][PILOT_MODEL_ID]
    assert pilot["task_profiles"]["tool_execution_agent"]["status"] == "NOT_APPROVED"


def test_search_profile_does_not_route_glm_when_benchmark_is_not_qualified(monkeypatch):
    monkeypatch.setattr(resolver_module, "_load_derived_matrix", lambda: _matrix())
    monkeypatch.setattr(
        "jamp.runtime.qualification.evaluate_model_qualification",
        lambda *_args, **_kwargs: "UNKNOWN",
    )

    eligible = CapabilityResolver().get_eligible_models("search_and_extraction")

    assert eligible[0] == "matrix/search-0"
    assert PILOT_MODEL_ID not in eligible
