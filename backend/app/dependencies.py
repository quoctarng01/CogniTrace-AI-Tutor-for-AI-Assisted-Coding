from functools import lru_cache
from typing import Optional

import httpx

from app.config import Settings, settings as app_settings
from app.repositories.supabase import SupabaseRepository


@lru_cache
def get_settings() -> Settings:
    return app_settings


async def get_supabase_repo() -> SupabaseRepository:
    settings = get_settings()
    repo = SupabaseRepository(settings)
    yield repo
    await repo.close()


async def get_profile_id_for_user(user_id: str) -> Optional[str]:
    """
    Map auth.users.id (UUID from JWT) → profiles.id (row PK in profiles table).

    Returns the profiles.id string if found, or None if the user has no profile.
    Does NOT raise an exception — callers decide what to do when None is returned.

    Usage:
        profile_id = await get_profile_id_for_user(user_id)
        if not profile_id:
            raise HTTPException(status_code=404, detail="User profile not found")
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{app_settings.supabase_url}/rest/v1/profiles",
            params={"user_id": f"eq.{user_id}", "select": "id"},
            headers={
                "Authorization": f"Bearer {app_settings.supabase_service_key}",
                "apikey": app_settings.supabase_service_key,
            },
        )
    if resp.status_code == 200:
        profiles = resp.json()
        if profiles:
            return profiles[0].get("id")
    return None


async def is_pro_user(user_id: str | None) -> bool:
    """
    Check if a user is on the Pro plan.

    Queries profiles table via Supabase REST API.
    Returns False on any error (fail-safe for rate limiting).

    Usage:
        pro = await is_pro_user(user_id)
        if not pro:
            # apply rate limit
    """
    if not user_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{app_settings.supabase_url}/rest/v1/profiles",
                params={"user_id": f"eq.{user_id}", "select": "plan"},
                headers={
                    "Authorization": f"Bearer {app_settings.supabase_service_key}",
                    "apikey": app_settings.supabase_service_key,
                },
            )
            if resp.status_code == 200:
                profiles = resp.json()
                if profiles and len(profiles) > 0:
                    return profiles[0].get("plan") == "pro"
    except Exception:
        pass
    return False

