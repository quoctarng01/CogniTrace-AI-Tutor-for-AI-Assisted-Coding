"""Explanation ratings API endpoints."""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import httpx

router = APIRouter(prefix="/api/ratings", tags=["ratings"])


class RatingRequest(BaseModel):
    explanation_id: Optional[str] = None
    trace_id: Optional[str] = None
    user_id: Optional[str] = None
    rating: int  # 1-5


@router.post("")
async def submit_rating(req: RatingRequest, authorization: str = Header(None)):
    """Submit a rating for an explanation."""
    if not 1 <= req.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")

    from app.config import settings

    # Extract user_id from auth header if available
    user_id = req.user_id
    if authorization and not user_id:
        from app.routers.auth import get_current_user
        try:
            user = await get_current_user(authorization)
            user_id = user.get("id")
        except Exception:
            pass

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/explanation_ratings",
            json={
                "explanation_id": req.explanation_id,
                "trace_id": req.trace_id,
                "user_id": user_id,
                "rating": req.rating,
            },
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
            },
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail="Failed to store rating")

    return {"status": "ok", "rating": req.rating}
