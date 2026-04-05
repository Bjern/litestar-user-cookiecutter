from app.lib.db import db_config, db_plugin


def test_db_config_has_connection_string() -> None:
    assert db_config.connection_string is not None


def test_db_config_session_key() -> None:
    assert db_config.session_dependency_key == "session"


def test_db_plugin_exists() -> None:
    assert db_plugin is not None
