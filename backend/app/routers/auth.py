# backend/app/routers/auth.py
"""
Supabase JWT verification — validates Bearer token and returns the user record.
Used as a dependency by other routers: Depends(get_current_user)
"""
from fastapi import HTTPException, Header
from typing import Optional
import httpx
import logging

logger = logging.getLogger("codescope.auth")

# ── Rate Limiter ────────────────────────────────────────────────
_limiter = None
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    _limiter = Limiter(key_func=get_remote_address)
except ImportError:
    pass  # slowapi not installed — rate limiting disabled


def _rate_limit(rate: str):
    """Decorator factory for rate limiting."""
    def decorator(func):
        if _limiter is None:
            return func
        return _limiter.limit(rate)(func)
    return decorator


def get_rate_limit(rate: str):
    """Dependency-based rate limiting."""
    if _limiter is None:
        return lambda: None
    return _limiter.limit(rate)


from fastapi import Request

async def get_current_user(request: Request, authorization: Optional[str] = Header(None)) -> dict:
    """
    Verify the Authorization: Bearer <token> header against Supabase.
    Returns the decoded user dict from Supabase /auth/v1/user.
    Raises HTTPException 401 if token is missing, invalid, or expired.
    """
    if not authorization:
        logger.warning("auth_no_header", extra={"location": "auth.py:get_current_user"})
        raise HTTPException(status_code=401, detail="Authorization header required")

    if not authorization.startswith("Bearer "):
        logger.warning("auth_invalid_format", extra={"location": "auth.py:get_current_user"})
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Use: Authorization: Bearer <token>",
        )

    token = authorization[7:]
    # Log token prefix (first 20 chars) for debugging - NEVER log full token
    logger.debug("auth_token_received")

    from app.config import settings
    logger.debug("auth_supabase_url", extra={"supabase_url": settings.supabase_url})

    client = request.app.state.http_client
    resp = await client.get(
        f"{settings.supabase_url}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": settings.supabase_service_key,
        },
    )
    logger.debug("auth_supabase_response", extra={"status_code": resp.status_code})

    if resp.status_code == 401:
        logger.warning("auth_token_invalid")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if resp.status_code != 200:
        logger.error("auth_failed", extra={"status_code": resp.status_code})
        raise HTTPException(status_code=401, detail="Authentication failed")

    user_data = resp.json()
    logger.info("auth_success", extra={"user_id": user_data.get("id", "")})
    return user_data


async def get_profile_id(token: str, client: httpx.AsyncClient | None = None) -> str:
    """
    Get the profiles.id for the authenticated user.
    token: JWT string AFTER 'Bearer ' prefix has been stripped.
    The auth user id maps to profiles.user_id.
    """
    from app.config import settings

    if client is not None:
        user_resp = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_service_key,
            },
        )
        if user_resp.status_code != 200:
            logger.warning("get_profile_id_auth_failed", extra={"status_code": user_resp.status_code})
            return ""
        
        user_id = user_resp.json().get("id", "")
        if not user_id:
            logger.warning("get_profile_id_no_uuid")
            return ""

        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            params={"user_id": f"eq.{user_id}", "select": "id"},
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
            },
        )
        if resp.status_code == 200:
            profiles = resp.json()
            if profiles and len(profiles) > 0:
                return profiles[0].get("id", "")
        return ""

    async with httpx.AsyncClient(timeout=10.0) as temp_client:
        # Step 1: Decode/verify token against Supabase auth to get the user UUID
        user_resp = await temp_client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_service_key,
            },
        )
        if user_resp.status_code != 200:
            logger.warning("get_profile_id_auth_failed", extra={"status_code": user_resp.status_code})
            return ""
        
        user_id = user_resp.json().get("id", "")
        if not user_id:
            logger.warning("get_profile_id_no_uuid")
            return ""

        # Step 2: Query profiles by user_id UUID
        resp = await temp_client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            params={"user_id": f"eq.{user_id}", "select": "id"},
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
            },
        )

    if resp.status_code == 200:
        profiles = resp.json()
        if profiles and len(profiles) > 0:
            return profiles[0].get("id", "")
    return ""

