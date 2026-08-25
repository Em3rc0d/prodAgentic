import copy
import hashlib

import httpx
import pytest

from core.linkedin import (
    LinkedInPublishError,
    LinkedInPublishPhase,
    LinkedInPublisher,
    LinkedInPublisherConfig,
    PublicationRetrySafety,
)
from core.publication import PublicationCoordinator, PublicationUnavailable
from models.content_run import ContentRunStatus


class ReadOnlyCollection:
    def __init__(self, doc):
        self.doc = copy.deepcopy(doc)
        self.update_calls = 0

    async def find_one(self, query):
        if query.get("run_id") != self.doc.get("run_id"):
            return None
        return copy.deepcopy(self.doc)

    async def update_one(self, query, update):
        self.update_calls += 1
        raise AssertionError("configuration failure must happen before PUBLISHING claim")


class ReadOnlyDb:
    def __init__(self, doc):
        self.collection = ReadOnlyCollection(doc)

    def __getitem__(self, name):
        assert name == "content_runs"
        return self.collection


def approved_doc():
    return {
        "run_id": "config-run",
        "status": ContentRunStatus.APPROVED.value,
        "approval": {
            "approval_id": "approval-config",
            "bundle_sha256": "bundle-config",
            "final_content": "approved text",
            "include_visual": False,
        },
        "publication": None,
    }


@pytest.mark.asyncio
async def test_invalid_config_fails_before_publishing_claim():
    db = ReadOnlyDb(approved_doc())

    def invalid_config():
        raise LinkedInPublishError(
            "missing LinkedIn configuration",
            retry_safety=PublicationRetrySafety.SAFE_TO_RETRY,
            phase=LinkedInPublishPhase.CONFIG,
        )

    coordinator = PublicationCoordinator(db, config_factory=invalid_config)
    with pytest.raises(PublicationUnavailable, match="missing LinkedIn configuration"):
        await coordinator.publish_run("config-run")

    assert db.collection.update_calls == 0
    assert db.collection.doc["status"] == ContentRunStatus.APPROVED.value
    assert db.collection.doc["publication"] is None


@pytest.mark.asyncio
async def test_image_upload_failure_is_safe_and_never_reaches_final_post(tmp_path):
    image_bytes = b"verified-image"
    renders = tmp_path / "renders"
    renders.mkdir()
    (renders / "asset.png").write_bytes(image_bytes)
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.method, str(request.url)))
        if str(request.url) == "https://api.linkedin.com/rest/images?action=initializeUpload":
            return httpx.Response(200, json={
                "value": {
                    "uploadUrl": "https://upload.linkedin.test/image",
                    "image": "urn:li:image:upload-test",
                }
            })
        if str(request.url) == "https://upload.linkedin.test/image":
            return httpx.Response(500)
        raise AssertionError("final post creation must not be reached after image upload failure")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = LinkedInPublisher(
            LinkedInPublisherConfig("secret", "urn:li:person:123", "202606"),
            client=client,
            asset_root=str(tmp_path),
        )
        with pytest.raises(LinkedInPublishError, match="image upload failed") as error:
            await publisher.publish({
                "final_content": "approved visual text",
                "include_visual": True,
                "visual_render": {
                    "asset_url": "/assets/renders/asset.png",
                    "asset_sha256": hashlib.sha256(image_bytes).hexdigest(),
                },
            })

    assert error.value.retry_safety == PublicationRetrySafety.SAFE_TO_RETRY
    assert error.value.phase == LinkedInPublishPhase.IMAGE_UPLOAD
    assert calls == [
        ("POST", "https://api.linkedin.com/rest/images?action=initializeUpload"),
        ("PUT", "https://upload.linkedin.test/image"),
    ]
