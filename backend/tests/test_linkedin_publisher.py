import hashlib
import json

import httpx
import pytest

from core.linkedin import (
    LinkedInPublishError,
    LinkedInPublishPhase,
    LinkedInPublisher,
    LinkedInPublisherConfig,
    PublicationRetrySafety,
)


@pytest.mark.asyncio
async def test_text_only_approval_posts_directly_to_current_posts_api(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        assert request.url == httpx.URL("https://api.linkedin.com/rest/posts")
        body = json.loads(request.content)
        assert body["author"] == "urn:li:person:123"
        assert body["commentary"] == "Approved post"
        assert "content" not in body
        assert request.headers["linkedin-version"] == "202606"
        assert request.headers["x-restli-protocol-version"] == "2.0.0"
        return httpx.Response(201, headers={"x-restli-id": "urn:li:share:999"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = LinkedInPublisher(
            LinkedInPublisherConfig("secret", "urn:li:person:123", "202606"),
            client=client,
            asset_root=str(tmp_path),
        )
        result = await publisher.publish({
            "final_content": "Approved post",
            "include_visual": False,
        })

    assert result.post_urn == "urn:li:share:999"
    assert result.image_urn is None
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_visual_approval_verifies_bytes_uploads_image_then_posts(tmp_path):
    image_bytes = b"approved-image-bytes"
    renders = tmp_path / "renders"
    renders.mkdir()
    (renders / "asset.png").write_bytes(image_bytes)
    expected_digest = hashlib.sha256(image_bytes).hexdigest()
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if str(request.url) == "https://api.linkedin.com/rest/images?action=initializeUpload":
            assert json.loads(request.content) == {"initializeUploadRequest": {"owner": "urn:li:person:123"}}
            return httpx.Response(200, json={"value": {"uploadUrl": "https://upload.linkedin.test/image", "image": "urn:li:image:abc"}})
        if str(request.url) == "https://upload.linkedin.test/image":
            assert request.method == "PUT"
            assert request.content == image_bytes
            assert request.headers["authorization"] == "Bearer secret"
            return httpx.Response(201)
        if str(request.url) == "https://api.linkedin.com/rest/posts":
            body = json.loads(request.content)
            assert body["content"]["media"]["id"] == "urn:li:image:abc"
            return httpx.Response(201, headers={"x-restli-id": "urn:li:share:1000"})
        raise AssertionError(f"Unexpected request {request.method} {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = LinkedInPublisher(
            LinkedInPublisherConfig("secret", "urn:li:person:123", "202606"),
            client=client,
            asset_root=str(tmp_path),
        )
        result = await publisher.publish({
            "final_content": "Approved visual post",
            "include_visual": True,
            "visual_render": {
                "asset_url": "/assets/renders/asset.png",
                "asset_sha256": expected_digest,
            },
        })

    assert result.post_urn == "urn:li:share:1000"
    assert result.image_urn == "urn:li:image:abc"
    assert [request.method for request in calls] == ["POST", "PUT", "POST"]


@pytest.mark.asyncio
async def test_blank_approval_is_safe_to_retry_before_any_post_request(tmp_path):
    called = False

    def handler(request: httpx.Request):
        nonlocal called
        called = True
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = LinkedInPublisher(
            LinkedInPublisherConfig("secret", "urn:li:person:123", "202606"),
            client=client,
            asset_root=str(tmp_path),
        )
        with pytest.raises(LinkedInPublishError) as error:
            await publisher.publish({"final_content": "   ", "include_visual": False})

    assert called is False
    assert error.value.retry_safety == PublicationRetrySafety.SAFE_TO_RETRY
    assert error.value.phase == LinkedInPublishPhase.LOCAL_VALIDATION


@pytest.mark.asyncio
async def test_digest_mismatch_stops_before_any_linkedin_request_and_is_safe(tmp_path):
    renders = tmp_path / "renders"
    renders.mkdir()
    (renders / "asset.png").write_bytes(b"changed-after-approval")
    called = False

    def handler(request: httpx.Request):
        nonlocal called
        called = True
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = LinkedInPublisher(
            LinkedInPublisherConfig("secret", "urn:li:person:123", "202606"),
            client=client,
            asset_root=str(tmp_path),
        )
        with pytest.raises(LinkedInPublishError, match="byte digest") as error:
            await publisher.publish({
                "final_content": "Do not publish stale media",
                "include_visual": True,
                "visual_render": {
                    "asset_url": "/assets/renders/asset.png",
                    "asset_sha256": hashlib.sha256(b"original").hexdigest(),
                },
            })

    assert called is False
    assert error.value.retry_safety == PublicationRetrySafety.SAFE_TO_RETRY
    assert error.value.phase == LinkedInPublishPhase.LOCAL_VALIDATION


@pytest.mark.asyncio
async def test_image_initialization_failure_is_safe_because_post_creation_was_not_attempted(tmp_path):
    image_bytes = b"approved-image-bytes"
    renders = tmp_path / "renders"
    renders.mkdir()
    (renders / "asset.png").write_bytes(image_bytes)
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        assert str(request.url) == "https://api.linkedin.com/rest/images?action=initializeUpload"
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = LinkedInPublisher(
            LinkedInPublisherConfig("secret", "urn:li:person:123", "202606"),
            client=client,
            asset_root=str(tmp_path),
        )
        with pytest.raises(LinkedInPublishError, match="initialization failed") as error:
            await publisher.publish({
                "final_content": "Approved visual post",
                "include_visual": True,
                "visual_render": {
                    "asset_url": "/assets/renders/asset.png",
                    "asset_sha256": hashlib.sha256(image_bytes).hexdigest(),
                },
            })

    assert len(calls) == 1
    assert error.value.retry_safety == PublicationRetrySafety.SAFE_TO_RETRY
    assert error.value.phase == LinkedInPublishPhase.IMAGE_INITIALIZE


@pytest.mark.asyncio
async def test_created_without_external_id_requires_reconciliation(tmp_path):
    def handler(request: httpx.Request):
        assert request.url == httpx.URL("https://api.linkedin.com/rest/posts")
        return httpx.Response(201)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = LinkedInPublisher(
            LinkedInPublisherConfig("secret", "urn:li:person:123", "202606"),
            client=client,
            asset_root=str(tmp_path),
        )
        with pytest.raises(LinkedInPublishError, match="no x-restli-id") as error:
            await publisher.publish({"final_content": "Potentially created", "include_visual": False})

    assert error.value.retry_safety == PublicationRetrySafety.RECONCILIATION_REQUIRED
    assert error.value.phase == LinkedInPublishPhase.POST_CREATE


@pytest.mark.asyncio
async def test_final_post_transport_timeout_requires_reconciliation(tmp_path):
    def handler(request: httpx.Request):
        assert request.url == httpx.URL("https://api.linkedin.com/rest/posts")
        raise httpx.ReadTimeout("response lost after request", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = LinkedInPublisher(
            LinkedInPublisherConfig("secret", "urn:li:person:123", "202606"),
            client=client,
            asset_root=str(tmp_path),
        )
        with pytest.raises(LinkedInPublishError, match="outcome is ambiguous") as error:
            await publisher.publish({"final_content": "Network ambiguity", "include_visual": False})

    assert error.value.retry_safety == PublicationRetrySafety.RECONCILIATION_REQUIRED
    assert error.value.phase == LinkedInPublishPhase.POST_CREATE


@pytest.mark.asyncio
async def test_unproven_non_201_post_response_is_conservatively_ambiguous(tmp_path):
    def handler(request: httpx.Request):
        assert request.url == httpx.URL("https://api.linkedin.com/rest/posts")
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = LinkedInPublisher(
            LinkedInPublisherConfig("secret", "urn:li:person:123", "202606"),
            client=client,
            asset_root=str(tmp_path),
        )
        with pytest.raises(LinkedInPublishError, match="unproven side-effect") as error:
            await publisher.publish({"final_content": "Provider ambiguity", "include_visual": False})

    assert error.value.retry_safety == PublicationRetrySafety.RECONCILIATION_REQUIRED
    assert error.value.phase == LinkedInPublishPhase.POST_CREATE
