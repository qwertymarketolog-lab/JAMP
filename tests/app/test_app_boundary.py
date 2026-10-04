from jamp_app.config import AppConfig


def test_app_boundary_imports_without_touching_core():
    config = AppConfig()
    assert config.name == "JAMP"
    assert config.version == "0.1.0"
