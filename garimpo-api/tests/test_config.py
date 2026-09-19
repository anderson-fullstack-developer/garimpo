import pytest

from app.config import Settings


def test_blank_optional_values_mean_not_configured(tmp_path):
    env = tmp_path / ".env"
    env.write_text("TURNSTILE_SECRET=\nCOOKIE_DOMAIN=   \nRESEND_API_KEY=\nTELEGRAM_BOT_TOKEN=\n")
    s = Settings(_env_file=env)
    assert s.turnstile_secret is None  # captcha desligado
    assert s.cookie_domain is None
    assert s.telegram_bot_token is None


def test_configured_values_are_kept(tmp_path):
    env = tmp_path / ".env"
    env.write_text("TURNSTILE_SECRET=abc123\nCOOKIE_DOMAIN=.exemplo.com\n")
    s = Settings(_env_file=env)
    assert s.turnstile_secret == "abc123" and s.cookie_domain == ".exemplo.com"


def test_production_refuses_insecure_defaults():
    with pytest.raises(ValueError):
        Settings(environment="production")  # segredo padrão
    with pytest.raises(ValueError):
        Settings(environment="production", jwt_secret="x" * 40, cookie_secure=False)
    ok = Settings(environment="production", jwt_secret="x" * 40, cookie_secure=True)
    assert ok.environment == "production"


def test_neon_urls_are_normalized_for_psycopg3():
    from app.db import normalize_url

    assert normalize_url("postgresql://u:p@h/db?sslmode=require") == "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert normalize_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_url("sqlite:///./x.db") == "sqlite:///./x.db"
