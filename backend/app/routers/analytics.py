from datetime import UTC, datetime

from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/analytics/track")
async def track_event(request: Request):
    """
    Saves an anonymous event to Supabase anonymous_events table.
    No auth required — anonymous by design.
    """
    import httpx

    from app.config import settings

    body = await request.json()
    anon_id = body.get("anon_id", "")
    event_type = body.get("event_type", "")
    metadata = body.get("metadata", {})
    occurred_at = body.get("occurred_at", datetime.now(UTC).isoformat())
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(
            f"{settings.supabase_url}/rest/v1/anonymous_events",
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "Content-Type": "application/json",
            },
            json={
                "anon_id": anon_id,
                "event_type": event_type,
                "metadata": metadata,
                "occurred_at": occurred_at,
            },
        )

    return {"ok": True}
