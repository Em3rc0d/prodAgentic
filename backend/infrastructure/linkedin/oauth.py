from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from core.linkedin_oauth import LinkedInOAuthSettings, LinkedInTokenCipher
from domain.tenants.models import TenantContext
from infrastructure.mongo.publishing import MongoConnectionRepository


class S10LinkedInOAuthError(RuntimeError):
    pass


class S10LinkedInOAuthService:
    AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
    STATE_TTL_SECONDS = 600

    def __init__(
        self,
        db,
        context: TenantContext,
        *,
        settings: LinkedInOAuthSettings | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self.db = db
        self.context = context
        self.settings = settings or LinkedInOAuthSettings.from_env()
        self.client = client
        self.cipher = LinkedInTokenCipher(self.settings.token_key)
        self.states = db["linkedin_oauth_states_v2"]

    async def _request(self, method: str, url: str, **kwargs):
        if self.client is not None:
            return await self.client.request(method, url, **kwargs)
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await client.request(method, url, **kwargs)

    @staticmethod
    def _state_digest(state: str) -> str:
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    async def ensure_indexes(self):
        await self.states.create_index("expires_at", expireAfterSeconds=0)
        await self.states.create_index(
            [("tenant_id", 1), ("state_sha256", 1)],
            unique=True,
            name="tenant_oauth_state_unique",
        )

    async def create_authorization_url(
        self,
        session_id: str,
        *,
        extra_scopes: tuple[str, ...] = (),
    ) -> str:
        await self.ensure_indexes()
        requested_scopes = sorted(
            set(self.settings.scopes).union(scope.strip() for scope in extra_scopes if scope.strip())
        )
        state = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        await self.states.insert_one(
            {
                "tenant_id": self.context.tenant_id,
                "state_sha256": self._state_digest(state),
                "session_id": session_id,
                "requested_scopes": requested_scopes,
                "created_at": now,
                "expires_at": now + timedelta(seconds=self.STATE_TTL_SECONDS),
            }
        )
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.settings.client_id,
                "redirect_uri": self.settings.redirect_uri,
                "state": state,
                "scope": " ".join(requested_scopes),
            }
        )
        return f"{self.AUTHORIZATION_URL}?{query}"

    async def _consume_state(self, state: str, session_id: str) -> dict[str, Any]:
        record = await self.states.find_one_and_delete(
            {
                "tenant_id": self.context.tenant_id,
                "state_sha256": self._state_digest(state),
                "session_id": session_id,
            }
        )
        if not record:
            raise S10LinkedInOAuthError("LinkedIn OAuth state is invalid or already used")
        expires_at = record.get("expires_at")
        if isinstance(expires_at, datetime) and (expires_at.tzinfo is None or expires_at.utcoffset() is None):
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if not isinstance(expires_at, datetime) or expires_at <= datetime.now(timezone.utc):
            raise S10LinkedInOAuthError("LinkedIn OAuth state has expired")
        return record

    async def complete_authorization(self, *, code: str, state: str, session_id: str) -> dict[str, Any]:
        if not code or not state:
            raise S10LinkedInOAuthError("LinkedIn callback is missing code or state")
        state_record = await self._consume_state(state, session_id)
        requested_scopes = set(state_record.get("requested_scopes") or self.settings.scopes)

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
            raise S10LinkedInOAuthError(
                f"LinkedIn token exchange failed with HTTP {token_response.status_code}"
            )
        try:
            token_payload = token_response.json()
            access_token = str(token_payload["access_token"]).strip()
            expires_in = int(token_payload["expires_in"])
        except (KeyError, TypeError, ValueError) as exc:
            raise S10LinkedInOAuthError("LinkedIn token exchange returned invalid data") from exc
        if not access_token or expires_in <= 0:
            raise S10LinkedInOAuthError("LinkedIn token exchange returned invalid lifetime")

        userinfo = await self._request(
            "GET",
            self.USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo.status_code != 200:
            raise S10LinkedInOAuthError(f"LinkedIn userinfo failed with HTTP {userinfo.status_code}")
        try:
            profile = userinfo.json()
            member_sub = str(profile["sub"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise S10LinkedInOAuthError("LinkedIn userinfo returned no member identity") from exc
        if not member_sub:
            raise S10LinkedInOAuthError("LinkedIn member identity is empty")

        raw_scope = token_payload.get("scope") or " ".join(sorted(requested_scopes))
        scopes = sorted(
            set(raw_scope.replace(",", " ").split())
            if isinstance(raw_scope, str)
            else requested_scopes
        )
        if not requested_scopes.issubset(scopes):
            missing = sorted(requested_scopes - set(scopes))
            raise S10LinkedInOAuthError(
                f"LinkedIn did not grant required scopes: {', '.join(missing)}"
            )

        now = datetime.now(timezone.utc)
        repo = MongoConnectionRepository(self.db, self.context)
        return await repo.upsert_linkedin_oauth(
            external_identity=f"urn:li:person:{member_sub}",
            display_name=profile.get("name") or "LinkedIn member",
            picture_url=profile.get("picture"),
            encrypted_access_token=self.cipher.encrypt(access_token),
            scopes=scopes,
            expires_at=now + timedelta(seconds=expires_in),
            connected_at=now,
        )
