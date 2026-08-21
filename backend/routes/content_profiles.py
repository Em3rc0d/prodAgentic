from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from db.mongo import get_db
from models.content_profile import ContentProfile, ContentProfileCreate, ContentProfileUpdate


router = APIRouter(tags=["content-profiles"])


def _serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


async def _set_single_default(collection, profile_id: str):
    await collection.update_many(
        {"profile_id": {"$ne": profile_id}},
        {"$set": {"is_default": False}},
    )


@router.get("/content-profiles")
async def list_content_profiles(include_archived: bool = Query(False)):
    db = get_db()
    if db is None:
        return {"profiles": [], "count": 0, "message": "MongoDB not connected"}
    query = {} if include_archived else {"archived": {"$ne": True}}
    cursor = db["content_profiles"].find(query).sort([("is_default", -1), ("updated_at", -1)])
    profiles = []
    async for doc in cursor:
        profiles.append(_serialize(doc))
    return {"profiles": profiles, "count": len(profiles)}


@router.get("/content-profiles/{profile_id}")
async def get_content_profile(profile_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    doc = await db["content_profiles"].find_one({"profile_id": profile_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="Content profile not found")
    return _serialize(doc)


@router.post("/content-profiles", status_code=201)
async def create_content_profile(req: ContentProfileCreate):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    collection = db["content_profiles"]
    now = datetime.now(timezone.utc)
    profile = ContentProfile(
        profile_id=str(uuid4()),
        **req.model_dump(),
        created_at=now,
        updated_at=now,
    )
    if profile.is_default:
        await _set_single_default(collection, profile.profile_id)
    await collection.insert_one(profile.model_dump())
    doc = await collection.find_one({"profile_id": profile.profile_id})
    return _serialize(doc)


@router.patch("/content-profiles/{profile_id}")
async def update_content_profile(profile_id: str, req: ContentProfileUpdate):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    collection = db["content_profiles"]
    existing = await collection.find_one({"profile_id": profile_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content profile not found")

    updates = req.model_dump(exclude_none=True)
    min_words = updates.get("min_words", existing.get("min_words", 150))
    max_words = updates.get("max_words", existing.get("max_words", 220))
    if min_words > max_words:
        raise HTTPException(status_code=422, detail="min_words cannot exceed max_words")

    if updates.get("is_default") is True:
        await _set_single_default(collection, profile_id)
    updates["updated_at"] = datetime.now(timezone.utc)
    updates["version"] = int(existing.get("version", 1)) + 1
    await collection.update_one({"profile_id": profile_id}, {"$set": updates})
    doc = await collection.find_one({"profile_id": profile_id})
    return _serialize(doc)


@router.post("/content-profiles/{profile_id}/default")
async def set_default_content_profile(profile_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    collection = db["content_profiles"]
    existing = await collection.find_one({"profile_id": profile_id, "archived": {"$ne": True}})
    if existing is None:
        raise HTTPException(status_code=404, detail="Active content profile not found")
    await _set_single_default(collection, profile_id)
    await collection.update_one(
        {"profile_id": profile_id},
        {"$set": {"is_default": True, "updated_at": datetime.now(timezone.utc)}},
    )
    doc = await collection.find_one({"profile_id": profile_id})
    return _serialize(doc)


@router.delete("/content-profiles/{profile_id}")
async def archive_content_profile(profile_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    collection = db["content_profiles"]
    existing = await collection.find_one({"profile_id": profile_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content profile not found")
    await collection.update_one(
        {"profile_id": profile_id},
        {"$set": {"archived": True, "is_default": False, "updated_at": datetime.now(timezone.utc)}},
    )
    return {"ok": True, "profile_id": profile_id}
