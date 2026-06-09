"""
LLM router — /api/llm/* endpoints (explanation streaming).
"""
from __future__ import annotations

import httpx
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Header, Request
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from app.services.llm_router import llm_router, LLMProvider
from app.services.rate_limit import check_rate_limit
from app.config import settings
from app.dependencies import is_pro_user, get_profile_id_for_user
from app.routers.auth import get_current_user

logger = logging.getLogger("codescope.llm")

router = APIRouter()


@router.get("/explain/stream")
async def stream_explanation(
    request: Request,
    code: str = Query(..., max_length=5000),
    line_number: int = Query(..., ge=1),
    line_content: str = Query(..., max_length=500),
    locals_json: str = Query(..., max_length=2000),
    ollama_endpoint: Optional[str] = Query(default=None, description="Optional Ollama endpoint override"),
    token: Optional[str] = Query(default=None, description="Optional JWT token override for SSE"),
    authorization: Optional[str] = Header(None),
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
    
    # 2. Extract user_id from token query parameter or auth header
    user_id = None
    jwt_token = token
    if not jwt_token and authorization and authorization.startswith("Bearer "):
        jwt_token = authorization[7:]
    
    custom_settings = None
    if jwt_token:
        from app.routers.auth import get_profile_id
        user_id = await get_profile_id(jwt_token)
        if user_id:
            from app.dependencies import get_profile_settings
            client = request.app.state.http_client if hasattr(request.app, "state") and hasattr(request.app.state, "http_client") else None
            custom_settings = await get_profile_settings(user_id, client)
    
    # 3. Rate limit check (only for anonymous/unauthenticated users)
    # Authenticated Pro users bypass rate limiting
    if not user_id or not await is_pro_user(user_id):
        # Use client IP for anonymous users so they have separate rate limit buckets.
        # For authenticated users, use the token suffix as key.
        client_ip = request.client.host if request.client else "unknown"
        rate_key = jwt_token[-32:] if jwt_token else client_ip
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
            kwargs = {}
            if custom_settings:
                if custom_settings.get("github_models_pat"):
                    kwargs["github_models_pat"] = custom_settings["github_models_pat"]
                if custom_settings.get("custom_api_url"):
                    kwargs["custom_api_url"] = custom_settings["custom_api_url"]
                if custom_settings.get("custom_api_key"):
                    kwargs["custom_api_key"] = custom_settings["custom_api_key"]
                if custom_settings.get("custom_api_model"):
                    kwargs["custom_api_model"] = custom_settings["custom_api_model"]
            async for token, provider in llm_router.stream_explain(
                code=code,
                line_number=line_number,
                line_content=line_content,
                locals_dict=locals_dict,
                ollama_endpoint=ollama_endpoint,
                **kwargs
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


class DiagnoseRequest(BaseModel):
    code: str
    checkpoint_type: str
    variable_name: Optional[str] = None
    correct_value: str
    user_prediction: str
    line_number: int
    trace_id: Optional[str] = None
    steps: Optional[list] = None


@router.post("/diagnose")
async def diagnose_checkpoint_error(
    req: DiagnoseRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Diagnose a student's incorrect state prediction.
    If authenticated, automatically creates a trace and review_card targeting the misconception.
    """
    # 0. Load custom profile settings if authenticated
    custom_settings = None
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization[7:]
            from app.routers.auth import get_profile_id
            from app.dependencies import get_profile_settings
            profile_id = await get_profile_id(token)
            if profile_id:
                custom_settings = await get_profile_settings(profile_id)
        except Exception:
            pass

    # 1. Run the LLM mismatch diagnosis
    kwargs = {}
    if custom_settings:
        if custom_settings.get("github_models_pat"):
            kwargs["github_models_pat"] = custom_settings["github_models_pat"]
        if custom_settings.get("custom_api_url"):
            kwargs["custom_api_url"] = custom_settings["custom_api_url"]
        if custom_settings.get("custom_api_key"):
            kwargs["custom_api_key"] = custom_settings["custom_api_key"]
        if custom_settings.get("custom_api_model"):
            kwargs["custom_api_model"] = custom_settings["custom_api_model"]
    diagnosis = await llm_router.diagnose_misconception(
        code=req.code,
        checkpoint_type=req.checkpoint_type,
        variable_name=req.variable_name,
        correct_value=req.correct_value,
        user_prediction=req.user_prediction,
        lineno=req.line_number,
        **kwargs
    )
    
    tag = diagnosis.get("tag", "general_logic_error")
    explanation = diagnosis.get("explanation", "Logic mismatch detected.")

    # 2. If user is authenticated, create review_card for this misconception
    if authorization and authorization.startswith("Bearer "):
        try:
            import secrets
            from datetime import date, timedelta
            
            token = authorization[7:]
            user = await get_current_user(authorization)
            user_id = user.get("id", "")
            profile_id = await get_profile_id_for_user(user_id)
            
            if profile_id:
                trace_id = req.trace_id
                
                # If trace_id is not provided but we have steps, save the trace first
                if not trace_id and req.steps:
                    share_token = secrets.token_hex(16)
                    trace_data = {
                        "user_id": profile_id,
                        "code": req.code,
                        "language": "python",
                        "concept_tags": [tag],
                        "is_public": False,
                        "share_token": share_token,
                        "steps": req.steps,
                    }
                    
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(
                            f"{settings.supabase_url}/rest/v1/traces",
                            headers={
                                "Authorization": f"Bearer {settings.supabase_service_key}",
                                "apikey": settings.supabase_service_key,
                                "Content-Type": "application/json",
                                "Prefer": "return=representation",
                            },
                            json=trace_data,
                        )
                        if resp.status_code in (200, 201):
                            data = resp.json()
                            trace_id = data[0].get("id") if isinstance(data, list) else data.get("id")
                
                # Now create the review card associated with this trace and misconception tag
                if trace_id:
                    next_review = (date.today() + timedelta(days=1)).isoformat()
                    card_data = {
                        "user_id": profile_id,
                        "trace_id": trace_id,
                        "concept_tag": tag,
                        "easiness_factor": 2.5,
                        "interval_days": 1,
                        "repetitions": 0,
                        "next_review_date": next_review,
                    }
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        await client.post(
                            f"{settings.supabase_url}/rest/v1/review_cards",
                            headers={
                                "Authorization": f"Bearer {settings.supabase_service_key}",
                                "apikey": settings.supabase_service_key,
                                "Content-Type": "application/json",
                                "Prefer": "return=minimal",
                            },
                            json=card_data,
                        )
                        logger.info("review_card_created_for_misconception", extra={"tag": tag, "profile_id": profile_id})
        except Exception as e:
            logger.error("failed_to_create_misconception_review_card", extra={"error": str(e)})

    return {
        "tag": tag,
        "explanation": explanation,
    }

