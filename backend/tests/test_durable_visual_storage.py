import hashlib
import os
import subprocess
import sys

import httpx
import pytest

from core.assets import get_asset_root, get_render_storage_dir, prepare_asset_root
from core.linkedin import LinkedInPublisher, LinkedInPublisherConfig


def test_configured_asset_root_survives_process_replacement(monkeypatch, tmp_path):
    asset_root = tmp_path / "durable-volume"
    monkeypatch.setenv("PRODAGENTIC_ASSET_ROOT", str(asset_root))

    first_root = prepare_asset_root()
    assert first_root == asset_root.resolve()
    assert get_render_storage_dir() == asset_root.resolve() / "renders"

    env = os.environ.copy()
    env["PRODAGENTIC_ASSET_ROOT"] = str(asset_root)
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from core.assets import get_render_storage_dir; "
                "p=get_render_storage_dir()/'restart-proof.bin'; "
                "p.write_bytes(b'approved-visual-bytes')"
            ),
        ],
        check=True,
        env=env,
    )

    # A different Python process can reopen the same mounted asset authority.
    reopened = get_render_storage_dir() / "restart-proof.bin"
    assert reopened.read_bytes() == b"approved-visual-bytes"
    assert get_asset_root() == asset_root.resolve()


@pytest.mark.asyncio
async def test_linkedin_publisher_reopens_exact_approved_bytes_from_configured_root(monkeypatch, tmp_path):
    asset_root = tmp_path / "durable-volume"
    monkeypatch.setenv("PRODAGENTIC_ASSET_ROOT", str(asset_root))
    image_bytes = b"approved-image-after-restart"
    render_path = get_render_storage_dir() / "approved.png"
    render_path.write_bytes(image_bytes)

    approval = {
        "final_content": "Production restart storage proof.",
        "include_visual": True,
        "visual_render": {
            "asset_url": "/assets/renders/approved.png",
            "asset_sha256": hashlib.sha256(image_bytes).hexdigest(),
        },
    }
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.method, str(request.url)))
        if str(request.url) == "https://api.linkedin.com/rest/images?action=initializeUpload":
            return httpx.Response(
                200,
                json={
                    "value": {
                        "uploadUrl": "https://upload.restart-proof/image",
                        "image": "urn:li:image:restart-proof",
                    }
                },
            )
        if str(request.url) == "https://upload.restart-proof/image":
            assert request.content == image_bytes
            return httpx.Response(201)
        if str(request.url) == "https://api.linkedin.com/rest/posts":
            return httpx.Response(201, headers={"x-restli-id": "urn:li:share:restart-proof"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = LinkedInPublisherConfig(
        access_token="test-token",
        author_urn="urn:li:person:restart-proof",
        api_version="202606",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        # No explicit asset_root is supplied: a fresh publisher instance must
        # resolve the same configured durable root used by the render process.
        result = await LinkedInPublisher(config, client=client).publish(approval)

    assert result.post_urn == "urn:li:share:restart-proof"
    assert result.image_urn == "urn:li:image:restart-proof"
    assert [method for method, _url in calls] == ["POST", "PUT", "POST"]
