from research.exp21.federation import federate_sources
from research.exp21.observation_source import ObservationSource


def test_federation_combines_two_sources_without_mutating_source_records() -> None:
    sources = (
        ObservationSource("ai-1", "model-a", ("obs-1",)),
        ObservationSource("ai-2", "model-b", ("obs-2",)),
    )
    result = federate_sources(sources)
    assert result == ("obs-1", "obs-2")
