import os
from urllib.parse import urlparse

from core.auth import AuthSettings


class DeploymentConfigurationError(ValueError):
    pass


def _enabled(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes"}


def _clean_origin(value: str, name: str) -> str:
    raw = value.strip().rstrip("/")
    if not raw:
        raise DeploymentConfigurationError(f"{name} is required when cross-origin auth is enabled")

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DeploymentConfigurationError(f"{name} must be an absolute HTTP(S) origin")
    if parsed.username or parsed.password:
        raise DeploymentConfigurationError(f"{name} must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise DeploymentConfigurationError(f"{name} must be an origin only, with no path, query, or fragment")

    loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not loopback:
        raise DeploymentConfigurationError(f"{name} must use HTTPS except for loopback development")
    return raw


def validate_cross_origin_auth(auth_settings: AuthSettings) -> None:
    """Fail closed when a browser-facing cross-origin deployment is misconfigured.

    This is deliberately opt-in because prodAgentic can also be hosted behind a
    same-origin reverse proxy. When enabled, the frontend and backend are on
    distinct browser origins and credentialed fetches require an exact CORS
    allow-list entry plus Secure/SameSite=None session cookies.
    """

    if not _enabled("PRODAGENTIC_CROSS_ORIGIN_AUTH"):
        return

    if not auth_settings.enabled:
        raise DeploymentConfigurationError(
            "PRODAGENTIC_CROSS_ORIGIN_AUTH requires PRODAGENTIC_AUTH_ENABLED=true"
        )
    if not auth_settings.cookie_secure:
        raise DeploymentConfigurationError(
            "Cross-origin auth requires PRODAGENTIC_COOKIE_SECURE=true"
        )
    if auth_settings.cookie_samesite != "none":
        raise DeploymentConfigurationError(
            "Cross-origin auth requires PRODAGENTIC_COOKIE_SAMESITE=none"
        )

    frontend_origin = _clean_origin(os.environ.get("FRONTEND_URL", ""), "FRONTEND_URL")
    cors_origins = {
        origin.strip().rstrip("/")
        for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    }
    if "*" in cors_origins:
        raise DeploymentConfigurationError(
            "Cross-origin credentialed auth must not use wildcard CORS"
        )
    if frontend_origin not in cors_origins:
        raise DeploymentConfigurationError(
            "CORS_ALLOWED_ORIGINS must include the exact FRONTEND_URL origin when cross-origin auth is enabled"
        )
