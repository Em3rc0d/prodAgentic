import pytest

from core.linkedin_oauth import LinkedInOAuthConfigurationError, LinkedInOAuthSettings


def configure_required_oauth(monkeypatch, frontend_url: str | None):
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "client-id")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv(
        "LINKEDIN_REDIRECT_URI",
        "https://api.prodagentic.example/api/integrations/linkedin/callback",
    )
    monkeypatch.setenv(
        "PRODAGENTIC_LINKEDIN_TOKEN_KEY",
        "oauth-token-key-that-is-long-enough-for-production-tests",
    )
    monkeypatch.setenv("LINKEDIN_API_VERSION", "202607")
    if frontend_url is None:
        monkeypatch.delenv("FRONTEND_URL", raising=False)
    else:
        monkeypatch.setenv("FRONTEND_URL", frontend_url)


def test_oauth_configuration_requires_explicit_frontend_origin(monkeypatch):
    configure_required_oauth(monkeypatch, None)

    with pytest.raises(LinkedInOAuthConfigurationError, match="FRONTEND_URL"):
        LinkedInOAuthSettings.from_env()


def test_oauth_configuration_accepts_https_frontend_origin(monkeypatch):
    configure_required_oauth(monkeypatch, "https://app.prodagentic.example/")

    settings = LinkedInOAuthSettings.from_env()

    assert settings.frontend_url == "https://app.prodagentic.example"


@pytest.mark.parametrize(
    "frontend_url",
    [
        "http://app.prodagentic.example",
        "https://user:pass@app.prodagentic.example",
        "https://app.prodagentic.example/publishing",
        "https://app.prodagentic.example?next=/publishing",
        "https://app.prodagentic.example#publishing",
    ],
)
def test_oauth_configuration_rejects_unsafe_frontend_origins(monkeypatch, frontend_url):
    configure_required_oauth(monkeypatch, frontend_url)

    with pytest.raises(LinkedInOAuthConfigurationError):
        LinkedInOAuthSettings.from_env()


def test_oauth_configuration_keeps_local_http_development_valid(monkeypatch):
    configure_required_oauth(monkeypatch, "http://127.0.0.1:3000")
    monkeypatch.setenv(
        "LINKEDIN_REDIRECT_URI",
        "http://127.0.0.1:8000/api/integrations/linkedin/callback",
    )

    settings = LinkedInOAuthSettings.from_env()

    assert settings.frontend_url == "http://127.0.0.1:3000"
