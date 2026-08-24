import os
from pathlib import Path
from urllib.parse import urlparse


class ProductionConfigurationError(RuntimeError):
    """Raised when a production process would start with an unsafe runtime contract."""


def _truthy(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes"}


def _https_origin(name: str, value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ProductionConfigurationError(f"{name} is required in production")
    try:
        parsed = urlparse(raw)
        _ = parsed.port
    except ValueError as exc:
        raise ProductionConfigurationError(f"{name} must be a valid HTTPS origin") from exc

    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ProductionConfigurationError(f"{name} must use an HTTPS origin in production")
    if parsed.username or parsed.password:
        raise ProductionConfigurationError(f"{name} must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ProductionConfigurationError(f"{name} must be an origin only (no path, query, or fragment)")

    return f"https://{parsed.netloc.lower()}"


def validate_production_environment() -> None:
    environment = os.environ.get("PRODAGENTIC_ENV", "development").strip().lower()
    if environment not in {"development", "test", "production"}:
        raise ProductionConfigurationError(
            "PRODAGENTIC_ENV must be development, test, or production"
        )
    if environment != "production":
        return

    if not _truthy("PRODAGENTIC_AUTH_ENABLED", "true"):
        raise ProductionConfigurationError("PRODAGENTIC_AUTH_ENABLED must be true in production")
    if not _truthy("PRODAGENTIC_COOKIE_SECURE", "true"):
        raise ProductionConfigurationError("PRODAGENTIC_COOKIE_SECURE must be true in production")

    same_site = os.environ.get("PRODAGENTIC_COOKIE_SAMESITE", "").strip().lower()
    if same_site != "none":
        raise ProductionConfigurationError(
            "PRODAGENTIC_COOKIE_SAMESITE must be none in production so authenticated cross-origin requests work"
        )

    frontend_origin = _https_origin("FRONTEND_URL", os.environ.get("FRONTEND_URL", ""))

    raw_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
    if not raw_origins:
        raise ProductionConfigurationError("CORS_ALLOWED_ORIGINS is required in production")
    if "*" in {value.strip() for value in raw_origins.split(",")}:
        raise ProductionConfigurationError("CORS_ALLOWED_ORIGINS must not contain * in production")

    allowed_origins = {
        _https_origin("CORS_ALLOWED_ORIGINS", value)
        for value in raw_origins.split(",")
        if value.strip()
    }
    if frontend_origin not in allowed_origins:
        raise ProductionConfigurationError(
            "CORS_ALLOWED_ORIGINS must explicitly include FRONTEND_URL in production"
        )

    asset_root = os.environ.get("PRODAGENTIC_ASSET_ROOT", "").strip()
    if not asset_root:
        raise ProductionConfigurationError("PRODAGENTIC_ASSET_ROOT is required in production")
    if not Path(asset_root).expanduser().is_absolute():
        raise ProductionConfigurationError("PRODAGENTIC_ASSET_ROOT must be an absolute path in production")

    if _truthy("LINKEDIN_STATIC_FALLBACK_ENABLED", "false"):
        raise ProductionConfigurationError(
            "LINKEDIN_STATIC_FALLBACK_ENABLED must be false in production"
        )
