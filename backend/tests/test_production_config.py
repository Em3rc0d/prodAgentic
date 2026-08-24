import pytest

from core.production import ProductionConfigurationError, validate_production_environment


VALID_PRODUCTION_ENV = {
    "PRODAGENTIC_ENV": "production",
    "PRODAGENTIC_AUTH_ENABLED": "true",
    "PRODAGENTIC_COOKIE_SECURE": "true",
    "PRODAGENTIC_COOKIE_SAMESITE": "none",
    "FRONTEND_URL": "https://app.prodagentic.example",
    "CORS_ALLOWED_ORIGINS": "https://app.prodagentic.example",
    "PRODAGENTIC_ASSET_ROOT": "/data/prodagentic/assets",
    "LINKEDIN_STATIC_FALLBACK_ENABLED": "false",
}


def apply_valid_production_env(monkeypatch):
    for key, value in VALID_PRODUCTION_ENV.items():
        monkeypatch.setenv(key, value)


def test_non_production_keeps_local_development_contract(monkeypatch):
    monkeypatch.setenv("PRODAGENTIC_ENV", "development")
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    validate_production_environment()


def test_valid_production_boundary_passes(monkeypatch):
    apply_valid_production_env(monkeypatch)
    validate_production_environment()


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("PRODAGENTIC_AUTH_ENABLED", "false", "AUTH_ENABLED"),
        ("PRODAGENTIC_COOKIE_SECURE", "false", "COOKIE_SECURE"),
        ("PRODAGENTIC_COOKIE_SAMESITE", "lax", "COOKIE_SAMESITE"),
        ("FRONTEND_URL", "http://app.prodagentic.example", "HTTPS origin"),
        ("FRONTEND_URL", "https://app.prodagentic.example/path", "origin only"),
        ("CORS_ALLOWED_ORIGINS", "*", "must not contain"),
        ("CORS_ALLOWED_ORIGINS", "http://app.prodagentic.example", "HTTPS origin"),
        ("CORS_ALLOWED_ORIGINS", "https://other.example", "include FRONTEND_URL"),
        ("PRODAGENTIC_ASSET_ROOT", "static/assets", "absolute path"),
        ("LINKEDIN_STATIC_FALLBACK_ENABLED", "true", "must be false"),
    ],
)
def test_unsafe_production_boundaries_fail_closed(monkeypatch, name, value, message):
    apply_valid_production_env(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ProductionConfigurationError, match=message):
        validate_production_environment()


def test_unknown_environment_name_fails_closed(monkeypatch):
    monkeypatch.setenv("PRODAGENTIC_ENV", "prodution")
    with pytest.raises(ProductionConfigurationError, match="development, test, or production"):
        validate_production_environment()
