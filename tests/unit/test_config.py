import pytest

from app.core.config import MissingSettingError, get_settings

REQUIRED_VARS = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "OPENAI_API_KEY",
)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_all_required(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("OPENAI_API_KEY", "key")


def test_missing_required_vars_raise(monkeypatch):
    for var in REQUIRED_VARS:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(MissingSettingError) as exc_info:
        get_settings()

    assert "POSTGRES_USER" in str(exc_info.value)
    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_settings_load_from_env(monkeypatch):
    _set_all_required(monkeypatch)
    monkeypatch.setenv("FORCE_REPROCESS", "true")

    settings = get_settings()

    assert settings.database_url == "postgresql+psycopg2://u:p@h:5432/d"
    assert settings.force_reprocess is True


def test_force_reprocess_defaults_false(monkeypatch):
    _set_all_required(monkeypatch)
    monkeypatch.delenv("FORCE_REPROCESS", raising=False)

    assert get_settings().force_reprocess is False


def test_settings_are_cached(monkeypatch):
    _set_all_required(monkeypatch)
    assert get_settings() is get_settings()
