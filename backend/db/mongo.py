import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

_client: AsyncIOMotorClient | None = None
_db = None


async def connect_db():
    global _client, _db
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    try:
        _client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=3000)
        await _client.admin.command("ping")
        _db = _client[os.getenv("MONGO_DB", "content_engine")]
        print("[OK] MongoDB connected successfully")
    except Exception as e:
        print(f"[WARN] MongoDB unavailable: {e} - running without persistence")
        _client = None
        _db = None


async def close_db():
    global _client
    if _client:
        _client.close()


def get_db():
    return _db


def database_ready() -> bool:
    return _client is not None and _db is not None
