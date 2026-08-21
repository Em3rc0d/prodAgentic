import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional


COOKIE_NAME = "prodagentic_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuthConfigurationError(ValueError):
    pass


class SessionValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AuthSettings:
    enabled: bool
    admin_user: str
    admin_password: str
    session_secret: str
    ttl_seconds: int
    cookie_secure: bool
    cookie_samesite: str

    @classmethod
    def from_env(cls) -> "AuthSettings":
        enabled = os.environ.get("PRODAGENTIC_AUTH_ENABLED", "true").strip().lower() in {"1", "true", "yes"}
        admin_user = os.environ.get("PRODAGENTIC_ADMIN_USER", "admin").strip() or "admin"
        admin_password = os.environ.get("PRODAGENTIC_ADMIN_PASSWORD", "")
        session_secret = os.environ.get("PRODAGENTIC_SESSION_SECRET", "")
        try:
            ttl_seconds = int(os.environ.get("PRODAGENTIC_SESSION_TTL_SECONDS", "43200"))
        except ValueError as exc:
            raise AuthConfigurationError("PRODAGENTIC_SESSION_TTL_SECONDS must be an integer") from exc
        if ttl_seconds < 300 or ttl_seconds > 604800:
            raise AuthConfigurationError("PRODAGENTIC_SESSION_TTL_SECONDS must be between 300 and 604800")

        cookie_secure = os.environ.get("PRODAGENTIC_COOKIE_SECURE", "true").strip().lower() in {"1", "true", "yes"}
        cookie_samesite = os.environ.get("PRODAGENTIC_COOKIE_SAMESITE", "lax").strip().lower()
        if cookie_samesite not in {"lax", "strict", "none"}:
            raise AuthConfigurationError("PRODAGENTIC_COOKIE_SAMESITE must be lax, strict, or none")
        if cookie_samesite == "none" and not cookie_secure:
            raise AuthConfigurationError("SameSite=None requires PRODAGENTIC_COOKIE_SECURE=true")

        if enabled:
            if len(admin_password) < 12:
                raise AuthConfigurationError("PRODAGENTIC_ADMIN_PASSWORD must be at least 12 characters when auth is enabled")
            if len(session_secret) < 32:
                raise AuthConfigurationError("PRODAGENTIC_SESSION_SECRET must be at least 32 characters when auth is enabled")

        return cls(
            enabled=enabled,
            admin_user=admin_user,
            admin_password=admin_password,
            session_secret=session_secret,
            ttl_seconds=ttl_seconds,
            cookie_secure=cookie_secure,
            cookie_samesite=cookie_samesite,
        )


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


class SessionManager:
    def __init__(self, settings: AuthSettings):
        self.settings = settings

    def issue(self) -> tuple[str, dict[str, Any]]:
        now = int(time.time())
        payload = {
            "sub": self.settings.admin_user,
            "iat": now,
            "exp": now + self.settings.ttl_seconds,
            "csrf": secrets.token_urlsafe(32),
            "sid": secrets.token_urlsafe(18),
        }
        body = _b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        signature = hmac.new(self.settings.session_secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        return f"{body}.{_b64encode(signature)}", payload

    def verify(self, token: Optional[str]) -> dict[str, Any]:
        if not token:
            raise SessionValidationError("Missing session")
        try:
            body, signature_value = token.split(".", 1)
            supplied_signature = _b64decode(signature_value)
        except Exception as exc:
            raise SessionValidationError("Malformed session") from exc

        expected = hmac.new(self.settings.session_secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(supplied_signature, expected):
            raise SessionValidationError("Invalid session signature")
        try:
            payload = json.loads(_b64decode(body))
        except Exception as exc:
            raise SessionValidationError("Invalid session payload") from exc

        if payload.get("sub") != self.settings.admin_user:
            raise SessionValidationError("Invalid session subject")
        if not isinstance(payload.get("exp"), int) or payload["exp"] <= int(time.time()):
            raise SessionValidationError("Session expired")
        if not isinstance(payload.get("csrf"), str) or len(payload["csrf"]) < 20:
            raise SessionValidationError("Session missing CSRF binding")
        return payload

    def credentials_match(self, username: str, password: str) -> bool:
        user_ok = hmac.compare_digest(username.encode("utf-8"), self.settings.admin_user.encode("utf-8"))
        password_ok = hmac.compare_digest(password.encode("utf-8"), self.settings.admin_password.encode("utf-8"))
        return user_ok and password_ok
