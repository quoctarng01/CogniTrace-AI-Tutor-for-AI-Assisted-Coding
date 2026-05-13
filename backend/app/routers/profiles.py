"""
Profiles router — user profile management.
"""
from __future__ import annotations

import logging
import httpx
from fastapi import APIRouter, HTTPException, Header

logger = logging.getLogger("codescope.profiles")

router = APIRouter()


@router.get("/me")
async def get_profile(authorization: str = Header(None)):
    """
    Get current user's profile.
    
    Auth: Required
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    
    from app.config import Settings
    settings = Settings()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            params={"user_id": f"eq.{token}", "select": "*"},
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
            },
        )
    
    if resp.status_code == 200:
        profiles = resp.json()
        if profiles and len(profiles) > 0:
            return profiles[0]
    
    raise HTTPException(status_code=404, detail="Profile not found")


@router.patch("/me")
async def update_profile(
    experience_level: str | None = None,
    ai_tools_usage: str | None = None,
    ollama_endpoint: str | None = None,
    authorization: str = Header(None),
):
    """
    Update current user's profile settings.
    
    Auth: Required
    
    Note: ollama_endpoint defaults to https://ollama.com/api for all new users.
          Setting it to localhost:11434 enables full local inference (no data leaves device).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    valid_ollama_endpoints = [
        "https://ollama.com/api",
        "http://localhost:11434",
    ]
    
    if ollama_endpoint and ollama_endpoint not in valid_ollama_endpoints:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_ENDPOINT", "message": "ollama_endpoint must be https://ollama.com/api or localhost:11434"},
        )
    
    if experience_level and experience_level not in ("student", "junior", "mid"):
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_EXPERIENCE", "message": "experience_level must be: student, junior, or mid"},
        )
    
    from app.config import Settings
    settings = Settings()
    token = authorization[7:]
    
    # Build update payload
    update_data = {}
    if experience_level is not None:
        update_data["experience_level"] = experience_level
    if ai_tools_usage is not None:
        update_data["ai_tools_usage"] = ai_tools_usage
    if ollama_endpoint is not None:
        update_data["ollama_endpoint"] = ollama_endpoint
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.patch(
            f"{settings.supabase_url}/rest/v1/profiles",
            params={"user_id": f"eq.{token}"},
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=update_data,
        )
    
    if resp.status_code == 200:
        profiles = resp.json()
        if profiles and len(profiles) > 0:
            return profiles[0]
    
    raise HTTPException(status_code=404, detail="Profile not found or update failed")
