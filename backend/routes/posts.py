from fastapi import APIRouter, HTTPException
from bson import ObjectId
from db.mongo import get_db

router = APIRouter(tags=["posts"])


@router.get("/posts")
async def get_posts():
    """Return all saved posts, newest first."""
    db = get_db()
    if db is None:
        return {"posts": [], "message": "MongoDB not connected — posts not persisted"}

    posts = []
    cursor = db["posts"].find().sort("created_at", -1).limit(50)
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if "created_at" in doc and hasattr(doc["created_at"], "isoformat"):
            doc["created_at"] = doc["created_at"].isoformat()
        posts.append(doc)

    return {"posts": posts, "count": len(posts)}


@router.patch("/posts/{post_id}/status")
async def update_status(post_id: str, status: str):
    """Update post status: DRAFT | PUBLISHED | ARCHIVED"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")

    valid = ["DRAFT", "PUBLISHED", "ARCHIVED"]
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")

    try:
        result = await db["posts"].update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"status": status}},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Post not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": f"Status updated to {status}"}


@router.delete("/posts/{post_id}")
async def delete_post(post_id: str):
    """Delete a post by ID."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")

    try:
        result = await db["posts"].delete_one({"_id": ObjectId(post_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Post not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Post deleted successfully"}
