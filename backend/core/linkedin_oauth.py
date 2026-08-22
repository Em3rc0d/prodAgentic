import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from core.linkedin import LinkedInPublishError, LinkedInPublisherConfig


class LinkedInOAuthError(RuntimeError):
    pass


class LinkedInOAuthConfigurationError(LinkedInOAuthError):
    pass


class LinkedInOAuthStateError(LinkedInOAuthError):
    pass


@dataclass(frozen=True)
class LinkedInOAuthSettings:
    client_id: str
    client_secret: str
    redirect_uri: str
    token_key: str
    api_version: str
    frontend_url: str
    scopes: tuple[str, ...] = ("openid", "profile", "email", "w_member_social")

    @classmethod
    def from_env(cls) -> "LinkedInOAuthSettings":
        values = {
            "LINKEDIN_CLIENT_ID": os.environ.get("LINKEDIN_CLIENT_ID", "").strip(),
            "LINKEDIN_CLIENT_SECRET": os.environ.get("LINKEDIN_CLIENT_SECRET", "").strip(),
            "LINKEDIN_REDIRECT_URI": os.environ.get("LINKEDIN_REDIRECT_URI", "").strip(),
            "PRODAGENTIC_LINKEDIN_TOKEN_KEY": os.environ.get("PRODAGENTIC_LINKEDIN_TOKEN_KEY", "").strip(),
            "LINKEDIN_API_VERSION": os.environ.get("LINKEDIN_API_VERSION", "").strip(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise LinkedInOAuthConfigurationError(
                f"LinkedIn OAuth is not configured: missing {', '.join(missing)}"
            )
        if len(values["PRODAGENTIC_LINKEDIN_TOKEN_KEY"]) < 32:
            raise LinkedInOAuthConfigurationError(
                "PRODAGENTIC_LINKEDIN_TOKEN_KEY must be at least 32 characters"
            )
        if len(values["LINKEDIN_API_VERSION"]) != 6 or not values["LINKEDIN_API_VERSION"].isdigit():
            raise LinkedInOAuthConfigurationError("LINKEDIN_API_VERSION must use YYYYMM format")
        return cls(
            client_id=values["LINKEDIN_CLIENT_ID"],
            client_secret=values["LINKEDIN_CLIENT_SECRET"],
            redirect_uri=values["LINKEDIN_REDIRECT_URI"],
            token_key=values["PRODAGENTIC_LINKEDIN_TOKEN_KEY"],
            api_version=values["LINKEDIN_API_VERSION"],
            frontend_url=os.environ.get("FRONTEND_URL", "http://localhost:3000").strip().rstrip("/"),
        )


class LinkedInTokenCipher:
    def __init__(self, secret: str):
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise LinkedInOAuthError("Stored LinkedIn access token cannot be decrypted") from exc


def _as_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class LinkedInOAuthService:
    AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
    CONNECTION_ID = "primary"
    STATE_TTL_SECONDS = 600

    def __init__(
        self,
        db,
        settings: Optional[LinkedInOAuthSettings] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.db = db
        self.settings = settings or LinkedInOAuthSettings.from_env()
        self.client = client
        self.cipher = LinkedInTokenCipher(self.settings.token_key)

    async def _request(self, method: str, url: str, **kwargs):
        if self.client is not None:
            return await self.client.request(method, url, **kwargs)
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await client.request(method, url, **kwargs)

    @staticmethod
    def _state_digest(state: str) -> str:
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    async def create_authorization_url(self, session_id: str) -> str:
        state = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        await self.db["linkedin_oauth_states"].insert_one({
            "state_sha256": self._state_digest(state),
            "session_id": session_id,
            "created_at": now,
            "expires_at": now + timedelta(seconds=self.STATE_TTL_SECONDS),
        })
        query = urlencode({
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": self.settings.redirect_uri,
            "state": state,
            "scope": " ".join(self.settings.scopes),
        })
        return f"{self.AUTHORIZATION_URL}?{query}"

    async def _consume_state(self, state: str, session_id: str) -> None:
        record = await self.db["linkedin_oauth_states"].find_one_and_delete({
            "state_sha256": self._state_digest(state),
            "session_id": session_id,
        })
        if not record:
            raise LinkedInOAuthStateError("LinkedIn OAuth state is invalid or was already used")
        expires_at = _as_utc(record.get("expires_at"))
        if expires_at is None or expires_at <= datetime.now(timezone.utc):
            raise LinkedInOAuthStateError("LinkedIn OAuth state has expired")

    async def complete_authorization(self, code: str, state: str, session_id: str) -> dict[str, Any]:
        if not code or not state:
            raise LinkedInOAuthError("LinkedIn callback is missing code or state")
        await self._consume_state(state, session_id)

        token_response = await self._request(
            "POST",
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "redirect_uri": self.settings.redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_response.status_code != 200:
            raise LinkedInOAuthError(
                f"LinkedIn token exchange failed with HTTP {token_response.status_code}"
            )
        try:
            token_payload = token_response.json()
            access_token = str(token_payload["access_token"]).strip()
            expires_in = int(token_payload["expires_in"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LinkedInOAuthError("LinkedIn token exchange returned an invalid response") from exc
        if not access_token or expires_in <= 0:
            raise LinkedInOAuthError("LinkedIn token exchange returned an invalid access token lifetime")

        userinfo_response = await self._request(
            "GET",
            self.USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_response.status_code != 200:
            raise LinkedInOAuthError(
                f"LinkedIn userinfo failed with HTTP {userinfo_response.status_code}"
            )
        try:
            profile = userinfo_response.json()
            member_sub = str(profile["sub"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise LinkedInOAuthError("LinkedIn userinfo returned no member identifier") from exc
        if not member_sub:
            raise LinkedInOAuthError("LinkedIn userinfo returned an empty member identifier")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expires_in)
        raw_scope = token_payload.get("scope") or " ".join(self.settings.scopes)
        if isinstance(raw_scope, str):
            scopes = sorted({scope for scope in raw_scope.replace(",", " ").split() if scope})
        else:
            scopes = list(self.settings.scopes)
        missing_scopes = [scope for scope in self.settings.scopes if scope not in scopes]
        if missing_scopes:
            raise LinkedInOAuthError(
                f"LinkedIn did not grant required scopes: {', '.join(missing_scopes)}"
            )

        connection = {
            "_id": self.CONNECTION_ID,
            "provider": "linkedin",
            "status": "CONNECTED",
            "member_sub": member_sub,
            "author_urn": f"urn:li:person:{member_sub}",
            "display_name": profile.get("name") or "LinkedIn member",
            "picture_url": profile.get("picture"),
            "encrypted_access_token": self.cipher.encrypt(access_token),
            "scopes": scopes,
            "connected_at": now,
            "updated_at": now,
            "expires_at": expires_at,
        }
        await self.db["linkedin_connections"].replace_one(
            {"_id": self.CONNECTION_ID}, connection, upsert=True
        )
        return connection

    async def get_connection(self) -> Optional[dict[str, Any]]:
        return await self.db["linkedin_connections"].find_one({"_id": self.CONNECTION_ID})

    async def status(self) -> dict[str, Any]:
        connection = await self.get_connection()
        if not connection:
            return {"configured": True, "connected": False, "status": "NOT_CONNECTED"}
        expires_at = _as_utc(connection.get("expires_at"))
        expired = expires_at is None or expires_at <= datetime.now(timezone.utc)
        return {
            "configured": True,
            "connected": not expired,
            "status": "RECONNECT_REQUIRED" if expired else "CONNECTED",
            "display_name": connection.get("display_name"),
            "picture_url": connection.get("picture_url"),
            "author_urn": connection.get("author_urn"),
            "expires_at": expires_at,
            "scopes": connection.get("scopes") or [],
            "api_version": self.settings.api_version,
        }

    async def disconnect(self) -> None:
        await self.db["linkedin_connections"].delete_one({"_id": self.CONNECTION_ID})

    async def publisher_config(self) -> LinkedInPublisherConfig:
        connection = await self.get_connection()
        if not connection:
            raise LinkedInPublishError("LinkedIn account is not connected")
        expires_at = _as_utc(connection.get("expires_at"))
        if expires_at is None or expires_at <= datetime.now(timezone.utc):
            raise LinkedInPublishError("LinkedIn connection expired; reconnect LinkedIn")
        required = set(self.settings.scopes)
        granted = set(connection.get("scopes") or [])
        if not required.issubset(granted):
            raise LinkedInPublishError("LinkedIn connection is missing required OAuth scopes")
        return LinkedInPublisherConfig(
            access_token=self.cipher.decrypt(connection["encrypted_access_token"]),
            author_urn=connection["author_urn"],
            api_version=self.settings.api_version,
        )
