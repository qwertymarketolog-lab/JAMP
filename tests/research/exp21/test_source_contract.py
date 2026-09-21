import pytest

from research.exp21.observation_source import ObservationSource


def test_source_rejects_empty_source_id() -> None:
    with pytest.raises(ValueError):
        ObservationSource(source_id="", model_id="model-a", observation_ids=("obs-1",))


def test_source_rejects_empty_model_id() -> None:
    with pytest.raises(ValueError):
        ObservationSource(source_id="ai-1", model_id="", observation_ids=("obs-1",))


def test_source_rejects_empty_observation_ids() -> None:
    with pytest.raises(ValueError):
        ObservationSource(source_id="ai-1", model_id="model-a", observation_ids=())


def test_source_contract_is_frozen() -> None:
    source = ObservationSource("ai-1", "model-a", ("obs-1",))
    with pytest.raises(AttributeError):
        source.source_id = "mutated"
