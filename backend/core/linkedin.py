import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

from core.assets import get_asset_root


class LinkedInPublishError(RuntimeError):
    pass


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
            raise LinkedInPublishError(f"LinkedIn publisher is not configured: missing {', '.join(missing)}")
        if not (author_urn.startswith("urn:li:person:") or author_urn.startswith("urn:li:organization:")):
            raise LinkedInPublishError("LINKEDIN_AUTHOR_URN must be a person or organization URN")
        if len(api_version) != 6 or not api_version.isdigit():
            raise LinkedInPublishError("LINKEDIN_API_VERSION must use YYYYMM format")
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

    def _api_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.access_token}",
            "Linkedin-Version": self.config.api_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    def _resolve_asset(self, asset_url: str) -> Path:
        if not asset_url.startswith("/assets/"):
            raise LinkedInPublishError("Approved visual does not reference a locally owned asset")
        relative = asset_url.removeprefix("/assets/")
        path = (self.asset_root / relative).resolve()
        if self.asset_root not in path.parents:
            raise LinkedInPublishError("Approved visual asset path is outside the storage boundary")
        if not path.is_file():
            raise LinkedInPublishError("Approved visual asset is missing from storage")
        return path

    def _read_verified_asset(self, visual: dict[str, Any]) -> bytes:
        expected = (visual.get("asset_sha256") or "").strip().lower()
        if not expected:
            raise LinkedInPublishError("Approved visual has no byte digest")
        asset_url = visual.get("asset_url") or ""
        path = self._resolve_asset(asset_url)
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise LinkedInPublishError("Approved visual byte digest does not match the stored file")
        return data

    async def _request(self, method: str, url: str, **kwargs):
        if self.client is not None:
            response = await self.client.request(method, url, **kwargs)
            return response
        async with httpx.AsyncClient(timeout=45.0) as client:
            return await client.request(method, url, **kwargs)

    async def _upload_image(self, image_bytes: bytes) -> str:
        initialize = await self._request(
            "POST",
            f"{self.API_BASE}/rest/images?action=initializeUpload",
            headers=self._api_headers(),
            json={"initializeUploadRequest": {"owner": self.config.author_urn}},
        )
        if initialize.status_code != 200:
            raise LinkedInPublishError(f"LinkedIn image initialization failed with HTTP {initialize.status_code}")
        try:
            value = initialize.json()["value"]
            upload_url = value["uploadUrl"]
            image_urn = value["image"]
        except (KeyError, TypeError, ValueError) as exc:
            raise LinkedInPublishError("LinkedIn image initialization returned an invalid response") from exc

        upload = await self._request(
            "PUT",
            upload_url,
            headers={
                "Authorization": f"Bearer {self.config.access_token}",
                "Content-Type": "application/octet-stream",
            },
            content=image_bytes,
        )
        if upload.status_code not in (200, 201, 202):
            raise LinkedInPublishError(f"LinkedIn image upload failed with HTTP {upload.status_code}")
        return image_urn

    async def publish(self, approval: dict[str, Any]) -> LinkedInPublicationResult:
        commentary = (approval.get("final_content") or "").strip()
        if not commentary:
            raise LinkedInPublishError("Approval contains no publishable final content")

        image_urn = None
        if approval.get("include_visual"):
            visual = approval.get("visual_render")
            if not isinstance(visual, dict):
                raise LinkedInPublishError("Approval requires a visual but no visual snapshot exists")
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

        response = await self._request(
            "POST",
            f"{self.API_BASE}/rest/posts",
            headers=self._api_headers(),
            json=body,
        )
        if response.status_code != 201:
            raise LinkedInPublishError(f"LinkedIn post creation failed with HTTP {response.status_code}")
        post_urn = response.headers.get("x-restli-id")
        if not post_urn:
            raise LinkedInPublishError("LinkedIn created the post but returned no x-restli-id evidence")
        return LinkedInPublicationResult(post_urn=post_urn, image_urn=image_urn)
