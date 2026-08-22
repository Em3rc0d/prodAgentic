import copy
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from core.linkedin_oauth import (
    LinkedInOAuthService,
    LinkedInOAuthSettings,
    LinkedInOAuthStateError,
)


class FakeCollection:
    def __init__(self):
        self.docs = []
        self.indexes = []

    async def create_index(self, key, **kwargs):
        self.indexes.append((key, kwargs))
        return key

    async def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

    async def find_one_and_delete(self, query):
        for index, doc in enumerate(self.docs):
            if all(doc.get(key) == value for key, value in query.items()):
                return self.docs.pop(index)
        return None

    async def replace_one(self, query, replacement, upsert=False):
        for index, doc in enumerate(self.docs):
            if all(doc.get(key) == value for key, value in query.items()):
                self.docs[index] = copy.deepcopy(replacement)
                return
        if upsert:
            self.docs.append(copy.deepcopy(replacement))

    async def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return copy.deepcopy(doc)
        return None

    async def delete_one(self, query):
        self.docs = [
            doc for doc in self.docs
            if not all(doc.get(key) == value for key, value in query.items())
        ]


class FakeDb:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


def settings(token_key="oauth-token-key-that-is-long-enough-for-tests"):
    return LinkedInOAuthSettings(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://localhost:8000/api/integrations/linkedin/callback",
        token_key=token_key,
        api_version="202607",
        frontend_url="http://localhost:3000",
    )


@pytest.mark.asyncio
async def test_oauth_state_is_session_bound_one_time_and_token_is_encrypted():
    db = FakeDb()

    def handler(request: httpx.Request):
        if str(request.url) == LinkedInOAuthService.TOKEN_URL:
            assert request.method == "POST"
            body = request.content.decode("utf-8")
            assert "client_secret=client-secret" in body
            assert "code=authorization-code" in body
            return httpx.Response(200, json={
                "access_token": "linkedin-real-access-token",
                "expires_in": 5184000,
                "scope": "openid profile w_member_social",
            })
        if str(request.url) == LinkedInOAuthService.USERINFO_URL:
            assert request.headers["authorization"] == "Bearer linkedin-real-access-token"
            return httpx.Response(200, json={
                "sub": "member-123",
                "name": "Test Member",
                "picture": "https://example.test/member.png",
                "email": "member@example.test",
                "email_verified": True,
            })
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = LinkedInOAuthService(db, settings=settings(), client=client)
        authorization_url = await service.create_authorization_url("session-1")
        query = parse_qs(urlparse(authorization_url).query)
        state = query["state"][0]
        assert query["client_id"] == ["client-id"]
        assert query["redirect_uri"] == [settings().redirect_uri]
        assert set(query["scope"][0].split()) == {"openid", "profile", "w_member_social"}
        assert db["linkedin_oauth_states"].indexes == [("expires_at", {"expireAfterSeconds": 0})]

        with pytest.raises(LinkedInOAuthStateError, match="invalid"):
            await service.complete_authorization("authorization-code", state, "different-session")

        connection = await service.complete_authorization("authorization-code", state, "session-1")
        assert connection["author_urn"] == "urn:li:person:member-123"
        assert connection["encrypted_access_token"] != "linkedin-real-access-token"
        assert "linkedin-real-access-token" not in connection["encrypted_access_token"]

        stored = await db["linkedin_connections"].find_one({"_id": "primary"})
        assert "email" not in stored
        assert "email_verified" not in stored
        assert stored["encrypted_access_token"] != "linkedin-real-access-token"

        status = await service.status()
        assert status["connected"] is True
        assert status["display_name"] == "Test Member"
        assert status["author_urn"] == "urn:li:person:member-123"
        assert "email" not in status

        config = await service.publisher_config()
        assert config.access_token == "linkedin-real-access-token"
        assert config.author_urn == "urn:li:person:member-123"
        assert config.api_version == "202607"

        with pytest.raises(LinkedInOAuthStateError, match="already used"):
            await service.complete_authorization("authorization-code", state, "session-1")


@pytest.mark.asyncio
async def test_disconnect_removes_publishing_authority_and_rotated_key_requires_reconnect():
    db = FakeDb()
    service = LinkedInOAuthService(db, settings=settings())
    now = datetime.now(timezone.utc)
    await db["linkedin_connections"].replace_one(
        {"_id": "primary"},
        {
            "_id": "primary",
            "status": "CONNECTED",
            "author_urn": "urn:li:person:member-123",
            "encrypted_access_token": service.cipher.encrypt("secret"),
            "scopes": ["openid", "profile", "w_member_social"],
            "expires_at": now.replace(year=now.year + 1).replace(tzinfo=None),
        },
        upsert=True,
    )

    assert (await service.status())["connected"] is True

    rotated = LinkedInOAuthService(
        db,
        settings=settings("a-different-oauth-token-key-that-is-long-enough"),
    )
    rotated_status = await rotated.status()
    assert rotated_status["connected"] is False
    assert rotated_status["status"] == "RECONNECT_REQUIRED"

    await service.disconnect()
    assert (await service.status())["connected"] is False
