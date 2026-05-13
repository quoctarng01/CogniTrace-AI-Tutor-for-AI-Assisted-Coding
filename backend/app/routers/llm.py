"""
LLM router — /api/llm/* endpoints (explanation streaming).
"""
from __future__ import annotations

import httpx
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Header
from fastapi.responses import Response
from sse_starlette.sse import EventSourceResponse

from app.services.llm_router import llm_router, LLMProvider
from app.services.rate_limit import check_rate_limit, RateLimitResult
from app.config import settings

logger = logging.getLogger("codescope.llm")

router = APIRouter()


@router.get("/explain/stream")
async def stream_explanation(
    code: str = Query(..., max_length=5000),
    line_number: int = Query(..., ge=1),
    line_content: str = Query(..., max_length=500),
    locals_json: str = Query(..., max_length=2000),
    user_id: Optional[str] = Query(None),  # For authenticated users
    ollama_endpoint: Optional[str] = Query(None),
    x_forwarded_for: str | None = Header(None),
):
    """
    Stream an LLM explanation for a specific line of code.
    
    Auth: Pro users (unlimited), anonymous users (rate-limited: 20/hour)
    Rate limit: Enforced per IP for anonymous users.
    
    Returns: Server-Sent Events stream of tokens.
    """
    # 1. Validate inputs
    if len(code) > 5000:
        raise HTTPException(
            status_code=422,
            detail={"error": "CODE_TOO_LONG", "message": "code exceeds 5000 characters"},
        )
    
    try:
        locals_dict = json.loads(locals_json)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_JSON", "message": "locals_json must be valid JSON"},
        )
    
    # 2. Rate limit check (only for anonymous/unauthenticated users)
    # Authenticated Pro users bypass rate limiting
    if not user_id or not await _is_pro_user(user_id):
        rate_key = x_forwarded_for or user_id or "anonymous"
        result = await check_rate_limit(rate_key)
        
        if not result.allowed:
            logger.warning(
                "rate_limit_exceeded",
                extra={"key": rate_key, "retry_after": result.retry_after_seconds},
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMITED",
                    "retry_after_seconds": result.retry_after_seconds,
                    "message": f"Rate limit exceeded. Try again in {result.retry_after_seconds} seconds. "
                               f"Upgrade to Pro for unlimited explanations.",
                },
                headers={"Retry-After": str(result.retry_after_seconds)},
            )
    
    # 3. Build SSE event generator
    async def event_generator():
        full_text = []
        provider_used = LLMProvider.GITHUB_MODELS
        error_occurred = False
        
        try:
            async for token, provider in llm_router.stream_explain(
                code=code,
                line_number=line_number,
                line_content=line_content,
                locals_dict=locals_dict,
                ollama_endpoint=ollama_endpoint,
            ):
                if token == "__done__":
                    break
                
                full_text.append(token)
                provider_used = provider
                
                yield {
                    "event": "message",
                    "data": json.dumps({"token": token, "provider": provider.value}),
                }
            
            # Done event
            yield {"event": "done", "data": json.dumps({"provider": provider_used.value})}
            
        except Exception as e:
            logger.error("sse_stream_error", extra={"error": str(e)})
            error_occurred = True
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": "EXPLANATION_UNAVAILABLE",
                    "message": "Failed to generate explanation. Please try again.",
                }),
            }
        
        # Log for metrics
        if full_text and not error_occurred:
            logger.info(
                "explanation_generated",
                extra={"provider": provider_used.value, "tokens": len(full_text)},
            )
    
    return EventSourceResponse(event_generator())


async def _is_pro_user(user_id: str | None) -> bool:
    """Check if user is on Pro plan by querying Supabase profiles table."""
    if not user_id:
        return False

    from app.config import settings
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/profiles",
                params={"user_id": f"eq.{user_id}", "select": "plan"},
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "apikey": settings.supabase_service_key,
                },
            )
            if resp.status_code == 200:
                profiles = resp.json()
                if profiles and len(profiles) > 0:
                    return profiles[0].get("plan") == "pro"
    except Exception:
        pass
    return False
