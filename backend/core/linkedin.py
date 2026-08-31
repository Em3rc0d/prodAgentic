import hashlib
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx

from core.assets import get_asset_root


class PublicationRetrySafety(str, Enum):
    SAFE_TO_RETRY = "SAFE_TO_RETRY"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class LinkedInPublishPhase(str, Enum):
    CONFIG = "CONFIG"
    LOCAL_VALIDATION = "LOCAL_VALIDATION"
    IMAGE_INITIALIZE = "IMAGE_INITIALIZE"
    IMAGE_UPLOAD = "IMAGE_UPLOAD"
    POST_CREATE = "POST_CREATE"
    UNKNOWN = "UNKNOWN"


class LinkedInPublishError(RuntimeError):
    """Provider failure carrying explicit retry-safety evidence.

    The conservative default is reconciliation-required. Callers must opt into
    SAFE_TO_RETRY only when the final external post-creation boundary is known
    not to have been reached.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_safety: PublicationRetrySafety = PublicationRetrySafety.RECONCILIATION_REQUIRED,
        phase: LinkedInPublishPhase = LinkedInPublishPhase.UNKNOWN,
    ):
        super().__init__(message)
        self.retry_safety = retry_safety
        self.phase = phase


@dataclass(frozen=True)
class LinkedInPublisherConfig:
    access_token: str
    author_urn: str
    api_version: str

    @classmethod
    def from_env(cls) -> "LinkedInPublisherConfig":
        access_token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip()
        author_urn = os.environ.get("LINKEDIN_AUTHOR_URN", "").strip()
        api_version = os.environ.get("LINKEDIN_API_VERSION", "").strip()
        missing = [
            name
            for name, value in (
                ("LINKEDIN_ACCESS_TOKEN", access_token),
                ("LINKEDIN_AUTHOR_URN", author_urn),
                ("LINKEDIN_API_VERSION", api_version),
            )
            if not value
        ]
        if missing:
            raise LinkedInPublishError(
                f"LinkedIn publisher is not configured: missing {', '.join(missing)}",
                retry_safety=PublicationRetrySafety.SAFE_TO_RETRY,
                phase=LinkedInPublishPhase.CONFIG,
            )
        if not (author_urn.startswith("urn:li:person:") or author_urn.startswith("urn:li:organization:")):
            raise LinkedInPublishError(
                "LINKEDIN_AUTHOR_URN must be a person or organization URN",
                retry_safety=PublicationRetrySafety.SAFE_TO_RETRY,
                phase=LinkedInPublishPhase.CONFIG,
            )
        if len(api_version) != 6 or not api_version.isdigit():
            raise LinkedInPublishError(
                "LINKEDIN_API_VERSION must use YYYYMM format",
                retry_safety=PublicationRetrySafety.SAFE_TO_RETRY,
                phase=LinkedInPublishPhase.CONFIG,
            )
        return cls(access_token=access_token, author_urn=author_urn, api_version=api_version)


@dataclass(frozen=True)
class LinkedInPublicationResult:
    post_urn: str
    image_urn: Optional[str] = None


class LinkedInPublisher:
    API_BASE = "https://api.linkedin.com"

    def __init__(
        self,
        config: LinkedInPublisherConfig,
        client: Optional[httpx.AsyncClient] = None,
        asset_root: str | Path | None = None,
    ):
        self.config = config
        self.client = client
        self.asset_root = (
            Path(asset_root).expanduser().resolve()
            if asset_root is not None
            else get_asset_root()
        )

    @staticmethod
    def _safe_error(message: str, phase: LinkedInPublishPhase) -> LinkedInPublishError:
        return LinkedInPublishError(
            message,
            retry_safety=PublicationRetrySafety.SAFE_TO_RETRY,
            phase=phase,
        )

    @staticmethod
    def _ambiguous_error(message: str, phase: LinkedInPublishPhase) -> LinkedInPublishError:
        return LinkedInPublishError(
            message,
            retry_safety=PublicationRetrySafety.RECONCILIATION_REQUIRED,
            phase=phase,
        )

    def _api_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.access_token}",
            "Linkedin-Version": self.config.api_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    def _resolve_asset(self, asset_url: str) -> Path:
        if not asset_url.startswith("/assets/"):
            raise self._safe_error(
                "Approved visual does not reference a locally owned asset",
                LinkedInPublishPhase.LOCAL_VALIDATION,
            )
        relative = asset_url.removeprefix("/assets/")
        path = (self.asset_root / relative).resolve()
        if self.asset_root not in path.parents:
            raise self._safe_error(
                "Approved visual asset path is outside the storage boundary",
                LinkedInPublishPhase.LOCAL_VALIDATION,
            )
        if not path.is_file():
            raise self._safe_error(
                "Approved visual asset is missing from storage",
                LinkedInPublishPhase.LOCAL_VALIDATION,
            )
        return path

    def _read_verified_asset(self, visual: dict[str, Any]) -> bytes:
        expected = (visual.get("asset_sha256") or "").strip().lower()
        if not expected:
            raise self._safe_error(
                "Approved visual has no byte digest",
                LinkedInPublishPhase.LOCAL_VALIDATION,
            )
        asset_url = visual.get("asset_url") or ""
        path = self._resolve_asset(asset_url)
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise self._safe_error(
                "Approved visual byte digest does not match the stored file",
                LinkedInPublishPhase.LOCAL_VALIDATION,
            )
        return data

    async def _request(self, method: str, url: str, **kwargs):
        if self.client is not None:
            return await self.client.request(method, url, **kwargs)
        async with httpx.AsyncClient(timeout=45.0) as client:
            return await client.request(method, url, **kwargs)

    async def _upload_image(self, image_bytes: bytes) -> str:
        try:
            initialize = await self._request(
                "POST",
                f"{self.API_BASE}/rest/images?action=initializeUpload",
                headers=self._api_headers(),
                json={"initializeUploadRequest": {"owner": self.config.author_urn}},
            )
        except Exception as exc:
            raise self._safe_error(
                "LinkedIn image initialization transport failed before post creation",
                LinkedInPublishPhase.IMAGE_INITIALIZE,
            ) from exc

        if initialize.status_code != 200:
            raise self._safe_error(
                f"LinkedIn image initialization failed with HTTP {initialize.status_code}",
                LinkedInPublishPhase.IMAGE_INITIALIZE,
            )
        try:
            value = initialize.json()["value"]
            upload_url = value["uploadUrl"]
            image_urn = value["image"]
        except (KeyError, TypeError, ValueError) as exc:
            raise self._safe_error(
                "LinkedIn image initialization returned an invalid response",
                LinkedInPublishPhase.IMAGE_INITIALIZE,
            ) from exc

        try:
            upload = await self._request(
                "PUT",
                upload_url,
                headers={
                    "Authorization": f"Bearer {self.config.access_token}",
                    "Content-Type": "application/octet-stream",
                },
                content=image_bytes,
            )
        except Exception as exc:
            raise self._safe_error(
                "LinkedIn image upload transport failed before post creation",
                LinkedInPublishPhase.IMAGE_UPLOAD,
            ) from exc

        if upload.status_code not in (200, 201, 202):
            raise self._safe_error(
                f"LinkedIn image upload failed with HTTP {upload.status_code}",
                LinkedInPublishPhase.IMAGE_UPLOAD,
            )
        return image_urn

    async def publish(self, approval: dict[str, Any]) -> LinkedInPublicationResult:
        commentary = (approval.get("final_content") or "").strip()
        if not commentary:
            raise self._safe_error(
                "Approval contains no publishable final content",
                LinkedInPublishPhase.LOCAL_VALIDATION,
            )

        image_urn = None
        if approval.get("include_visual"):
            visual = approval.get("visual_render")
            if not isinstance(visual, dict):
                raise self._safe_error(
                    "Approval requires a visual but no visual snapshot exists",
                    LinkedInPublishPhase.LOCAL_VALIDATION,
                )
            image_bytes = self._read_verified_asset(visual)
            image_urn = await self._upload_image(image_bytes)

        body: dict[str, Any] = {
            "author": self.config.author_urn,
            "commentary": commentary,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if image_urn:
            body["content"] = {"media": {"id": image_urn}}

        try:
            response = await self._request(
                "POST",
                f"{self.API_BASE}/rest/posts",
                headers=self._api_headers(),
                json=body,
            )
        except Exception as exc:
            raise self._ambiguous_error(
                "LinkedIn post creation transport outcome is ambiguous",
                LinkedInPublishPhase.POST_CREATE,
            ) from exc

        # Until provider-contract evidence proves a non-201 response cannot have
        # produced a side effect, hard duplicate safety treats it conservatively.
        if response.status_code != 201:
            raise self._ambiguous_error(
                f"LinkedIn post creation returned HTTP {response.status_code} with unproven side-effect outcome",
                LinkedInPublishPhase.POST_CREATE,
            )
        post_urn = response.headers.get("x-restli-id")
        if not post_urn:
            raise self._ambiguous_error(
                "LinkedIn created the post but returned no x-restli-id evidence",
                LinkedInPublishPhase.POST_CREATE,
            )
        return LinkedInPublicationResult(post_urn=post_urn, image_urn=image_urn)
