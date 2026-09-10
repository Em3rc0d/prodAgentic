from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from core.linkedin_oauth import LinkedInOAuthSettings, LinkedInTokenCipher
from domain.publishing.models import (
    PlatformCapabilityV1,
    PublicationReceiptV1,
    PublicationV1,
    canonical_sha256,
)


class PlatformSafeFailure(RuntimeError):
    """Provider outcome proves no public post was created."""


class PlatformUncertainFailure(RuntimeError):
    """The external request may have succeeded; automatic retry is unsafe."""


@dataclass(frozen=True)
class PreparedPublication:
    commentary: str
    image_bytes: bytes | None
    image_sha256: str | None
    image_content_type: str | None
    approval_bundle_sha256: str


class LinkedInPlatformAdapter:
    API_BASE = "https://api.linkedin.com"

    def __init__(self, *, settings: LinkedInOAuthSettings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client
        self._cipher_instance: LinkedInTokenCipher | None = None

    def _resolved_settings(self) -> LinkedInOAuthSettings:
        if self.settings is None:
            self.settings = LinkedInOAuthSettings.from_env()
        return self.settings

    def _cipher(self) -> LinkedInTokenCipher:
        if self._cipher_instance is None:
            self._cipher_instance = LinkedInTokenCipher(self._resolved_settings().token_key)
        return self._cipher_instance

    async def _request(self, method: str, url: str, **kwargs):
        if self.client is not None:
            return await self.client.request(method, url, **kwargs)
        async with httpx.AsyncClient(timeout=45.0) as client:
            return await client.request(method, url, **kwargs)

    def _token(self, connection: dict[str, Any]) -> str:
        encrypted = str(connection.get("encrypted_access_token") or "")
        if not encrypted:
            raise PlatformSafeFailure("LinkedIn connection has no encrypted token authority")
        try:
            return self._cipher().decrypt(encrypted)
        except Exception as exc:
            raise PlatformSafeFailure("LinkedIn connection cannot be decrypted; reconnect LinkedIn") from exc

    def _headers(self, token: str, *, content_type: str = "application/json") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Linkedin-Version": self._resolved_settings().api_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": content_type,
        }

    async def capabilities(self, connection: dict[str, Any]) -> PlatformCapabilityV1:
        now = datetime.now(timezone.utc)
        try:
            settings = self._resolved_settings()
        except Exception as exc:
            return PlatformCapabilityV1(
                connected=False,
                can_publish=False,
                supports_text=True,
                supports_single_image=True,
                supports_multi_image=False,
                can_reconcile=False,
                external_identity=connection.get("external_identity"),
                api_version=None,
                observed_at=now,
                reason=f"LinkedIn provider configuration unavailable: {exc}",
            )
        expires_at = connection.get("expires_at")
        if isinstance(expires_at, datetime) and (expires_at.tzinfo is None or expires_at.utcoffset() is None):
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        granted = set(connection.get("scopes") or [])
        required = {"openid", "profile", "w_member_social"}
        reason = None
        if connection.get("status") != "CONNECTED":
            reason = "LinkedIn connection is not connected"
        elif not isinstance(expires_at, datetime) or expires_at <= now:
            reason = "LinkedIn connection expired; reconnect LinkedIn"
        elif not required.issubset(granted):
            reason = "LinkedIn connection is missing required OAuth scopes"
        else:
            try:
                self._token(connection)
            except PlatformSafeFailure as exc:
                reason = str(exc)
        connected = reason is None
        return PlatformCapabilityV1(
            connected=connected,
            can_publish=connected,
            supports_text=True,
            supports_single_image=True,
            supports_multi_image=False,
            can_reconcile=connected,
            external_identity=connection.get("external_identity"),
            api_version=settings.api_version,
            observed_at=now,
            reason=reason,
        )

    async def _upload_image(self, *, token: str, owner: str, data: bytes) -> str:
        try:
            init = await self._request(
                "POST",
                f"{self.API_BASE}/rest/images?action=initializeUpload",
                headers=self._headers(token),
                json={"initializeUploadRequest": {"owner": owner}},
            )
        except httpx.RequestError as exc:
            raise PlatformSafeFailure("LinkedIn image initialization transport failed before post creation") from exc
        if init.status_code != 200:
            raise PlatformSafeFailure(f"LinkedIn image initialization failed with HTTP {init.status_code}")
        try:
            value = init.json()["value"]
            upload_url = value["uploadUrl"]
            image_urn = value["image"]
        except (KeyError, TypeError, ValueError) as exc:
            raise PlatformSafeFailure("LinkedIn image initialization returned invalid evidence") from exc
        try:
            upload = await self._request(
                "PUT",
                upload_url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
                content=data,
            )
        except httpx.RequestError as exc:
            raise PlatformSafeFailure("LinkedIn image upload transport failed before post creation") from exc
        if upload.status_code not in {200, 201, 202}:
            raise PlatformSafeFailure(f"LinkedIn image upload failed with HTTP {upload.status_code}")
        return str(image_urn)

    async def publish(self, prepared: PreparedPublication, connection: dict[str, Any]) -> PublicationReceiptV1:
        capability = await self.capabilities(connection)
        if not capability.can_publish:
            raise PlatformSafeFailure(capability.reason or "LinkedIn automatic publication unavailable")
        owner = str(connection.get("external_identity") or "")
        if not owner.startswith(("urn:li:person:", "urn:li:organization:")):
            raise PlatformSafeFailure("LinkedIn connection external identity is invalid")
        token = self._token(connection)
        image_urn = None
        if prepared.image_bytes is not None:
            if not prepared.image_sha256 or hashlib.sha256(prepared.image_bytes).hexdigest() != prepared.image_sha256:
                raise PlatformSafeFailure("prepared LinkedIn image bytes failed SHA-256 verification")
            image_urn = await self._upload_image(token=token, owner=owner, data=prepared.image_bytes)
        body: dict[str, Any] = {
            "author": owner,
            "commentary": prepared.commentary,
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if image_urn:
            body["content"] = {"media": {"id": image_urn}}
        try:
            response = await self._request("POST", f"{self.API_BASE}/rest/posts", headers=self._headers(token), json=body)
        except httpx.RequestError as exc:
            raise PlatformUncertainFailure("LinkedIn post request lost outcome certainty") from exc
        if response.status_code >= 500 or response.status_code in {408}:
            raise PlatformUncertainFailure(
                f"LinkedIn post creation returned HTTP {response.status_code} with uncertain side-effect outcome"
            )
        if response.status_code != 201:
            raise PlatformSafeFailure(f"LinkedIn post creation failed with HTTP {response.status_code}")
        post_urn = response.headers.get("x-restli-id")
        if not post_urn:
            raise PlatformUncertainFailure("LinkedIn accepted post request but returned no x-restli-id evidence")
        received_at = datetime.now(timezone.utc)
        payload = {
            "schema_version": 1,
            "provider": "linkedin",
            "external_post_id": post_urn,
            "external_asset_ids": tuple([image_urn] if image_urn else []),
            "provider_api_version": self._resolved_settings().api_version,
            "received_at": received_at,
        }
        return PublicationReceiptV1(**payload, receipt_digest=canonical_sha256(payload))

    async def reconcile(self, publication: PublicationV1, connection: dict[str, Any]) -> PublicationReceiptV1 | None:
        if not publication.external_post_id:
            return None
        capability = await self.capabilities(connection)
        if not capability.connected:
            return None
        token = self._token(connection)
        encoded = quote(publication.external_post_id, safe="")
        try:
            response = await self._request("GET", f"{self.API_BASE}/rest/posts/{encoded}", headers=self._headers(token))
        except httpx.RequestError:
            return None
        if response.status_code != 200:
            return None
        received_at = datetime.now(timezone.utc)
        payload = {
            "schema_version": 1,
            "provider": "linkedin",
            "external_post_id": publication.external_post_id,
            "external_asset_ids": publication.external_asset_ids,
            "provider_api_version": self._resolved_settings().api_version,
            "received_at": received_at,
        }
        return PublicationReceiptV1(**payload, receipt_digest=canonical_sha256(payload))
