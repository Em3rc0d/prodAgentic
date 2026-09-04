import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

_client: AsyncIOMotorClient | None = None
_db = None
_bootstrap_migration_report = None


async def _ensure_indexes(db):
    """Install persistence invariants before any publication worker can run."""
    await db["content_runs"].create_index(
        "publication.dedupe_key",
        unique=True,
        sparse=True,
        name="publication_dedupe_key_unique",
    )


async def _ensure_mk1_foundation_indexes(db):
    """Install S0 indexes without changing the legacy index-test contract."""
    await db["tenants"].create_index(
        "tenant_id",
        unique=True,
        name="tenant_id_unique",
    )
    for collection_name in ("content_profiles", "content_runs", "posts", "linkedin_connections"):
        await db[collection_name].create_index(
            "tenant_id",
            name=f"{collection_name}_tenant_id",
        )


async def connect_db(*, run_bootstrap_migration: bool = True):
    global _client, _db, _bootstrap_migration_report
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    try:
        _client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=3000)
        await _client.admin.command("ping")
        _db = _client[os.getenv("MONGO_DB", "content_engine")]
        await _ensure_indexes(_db)
        await _ensure_mk1_foundation_indexes(_db)
        if run_bootstrap_migration:
            from application.tenancy.bootstrap import migrate_bootstrap_tenant
            report = await migrate_bootstrap_tenant(_db)
            if not report.verified:
                raise RuntimeError("MK1 bootstrap tenant migration verification failed")
            _bootstrap_migration_report = report
            print(
                "[OK] MK1 bootstrap tenant verified "
                f"tenant_id={report.tenant_id} modified={sum(report.modified_by_collection.values())}"
            )
        print("[OK] MongoDB connected successfully")
    except Exception as e:
        print(f"[WARN] MongoDB unavailable: {e} - running without persistence")
        if _client:
            _client.close()
        _client = None
        _db = None
        _bootstrap_migration_report = None


async def close_db():
    global _client
    if _client:
        _client.close()


def get_db():
    return _db


def database_ready() -> bool:
    return _client is not None and _db is not None


def get_bootstrap_migration_report():
    return _bootstrap_migration_report
