from jamp_plugin.engine import ExampleEngine


def test_plugin_does_not_mutate_input() -> None:
    observation = {"question": "x"}
    before = dict(observation)
    result = ExampleEngine().propose(observation)
    assert observation == before
    assert result[0]["observation"] == before
