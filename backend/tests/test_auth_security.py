import time

import pytest

from core.auth import AuthConfigurationError, AuthSettings, SessionManager, SessionValidationError


def settings(**changes):
    values = {"enabled": True, "admin_user": "admin", "admin_password": "correct-horse-battery", "session_secret": "s" * 32, "ttl_seconds": 3600, "cookie_secure": True, "cookie_samesite": "lax"}
    values.update(changes)
    return AuthSettings(**values)


def test_session_round_trip_and_csrf_binding():
    manager = SessionManager(settings())
    token, issued = manager.issue()
    verified = manager.verify(token)
    assert verified["sub"] == "admin"
    assert verified["csrf"] == issued["csrf"]
    assert len(verified["sid"]) >= 20


def test_tampered_session_is_rejected():
    manager = SessionManager(settings())
    token, _ = manager.issue()
    body, signature = token.split(".", 1)
    with pytest.raises(SessionValidationError, match="signature"):
        manager.verify(f"{body}x.{signature}")


def test_expired_session_is_rejected(monkeypatch):
    manager = SessionManager(settings(ttl_seconds=300))
    token, issued = manager.issue()
    monkeypatch.setattr(time, "time", lambda: issued["exp"] + 1)
    with pytest.raises(SessionValidationError, match="expired"):
        manager.verify(token)


def test_credentials_require_both_values():
    manager = SessionManager(settings())
    assert manager.credentials_match("admin", "correct-horse-battery")
    assert not manager.credentials_match("admin", "wrong")
    assert not manager.credentials_match("other", "correct-horse-battery")


def test_enabled_auth_fails_closed_on_weak_secrets(monkeypatch):
    monkeypatch.setenv("PRODAGENTIC_AUTH_ENABLED", "true")
    monkeypatch.setenv("PRODAGENTIC_ADMIN_PASSWORD", "short")
    monkeypatch.setenv("PRODAGENTIC_SESSION_SECRET", "short")
    with pytest.raises(AuthConfigurationError):
        AuthSettings.from_env()
