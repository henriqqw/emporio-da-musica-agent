import pytest

from emporio.config import load_settings


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch):
    # isolate from a developer's local .env
    monkeypatch.setattr("emporio.config.load_dotenv", lambda *_: None)


def test_defaults(monkeypatch):
    for var in ("LLM_MODEL", "LLM_API_KEY", "REFERENCE_DATE", "SESSION_TTL_MINUTES"):
        monkeypatch.delenv(var, raising=False)
    settings = load_settings()
    assert settings.model == "gemini-flash-lite-latest"
    assert settings.session_ttl_minutes == 30
    assert settings.reference_date is None
    assert settings.llm_api_key == ""


def test_values_from_the_environment(monkeypatch):
    monkeypatch.setenv("REFERENCE_DATE", "2026-03-25")
    monkeypatch.setenv("SESSION_TTL_MINUTES", " ")  # blank means default
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    settings = load_settings()
    assert str(settings.reference_date) == "2026-03-25"
    assert settings.session_ttl_minutes == 30
    assert settings.reasoning_effort == "low"


@pytest.mark.parametrize("value", ["abc", "0", "-5"])
def test_invalid_ttl_has_a_clear_message(monkeypatch, value):
    monkeypatch.setenv("SESSION_TTL_MINUTES", value)
    with pytest.raises(ValueError, match="SESSION_TTL_MINUTES"):
        load_settings()


def test_api_key_is_not_in_repr(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret-123")
    assert "secret-123" not in repr(load_settings())
