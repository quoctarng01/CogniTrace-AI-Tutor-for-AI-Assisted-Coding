"""
LLM router — /api/llm/* endpoints (explanation streaming).
"""
from __future__ import annotations

import json
import logging

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.dependencies import get_profile_id_for_user, is_pro_user
from app.routers.auth import get_current_user
from app.services.llm_router import LLMProvider, llm_router
from app.services.rate_limit import check_rate_limit

logger = logging.getLogger("codescope.llm")

router = APIRouter()


@router.get("/explain/stream")
async def stream_explanation(
    request: Request,
    code: str = Query(..., max_length=5000),
    line_number: int = Query(..., ge=1),
    line_content: str = Query(..., max_length=500),
    locals_json: str = Query(..., max_length=2000),
    ollama_endpoint: str | None = Query(default=None, description="Optional Ollama endpoint override"),
    token: str | None = Query(default=None, description="Optional JWT token override for SSE"),
    authorization: str | None = Header(None),
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
    variable_name: str | None = None
    correct_value: str
    user_prediction: str
    line_number: int
    trace_id: str | None = None
    steps: list | None = None
    # T1-C: Adaptive Checkpoint Difficulty
    # ------------------------------------------------------------------
    # `concept_tag`     — the SM-2 concept for the current checkpoint.
    # `checkpoint_mode` — one of "direct" | "scaffolded" | "contrastive".
    #                     When omitted, the backend runs the selector
    #                     over the student's recent reviews and chooses
    #                     a mode based on the THESIS-05 §3 rubric.
    # `override_mode`   — set true to bypass the selector (debug / A/B
    #                     experiment arm where the mode is fixed).
    concept_tag: str | None = None
    checkpoint_mode: str | None = None
    override_mode: bool = False


@router.post("/diagnose")
async def diagnose_checkpoint_error(
    req: DiagnoseRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    """
    Diagnose a student's incorrect state prediction.
    If authenticated, automatically creates a trace and review_card targeting the misconception.

    T1-C: When the request carries `concept_tag` (or `checkpoint_mode`)
    we pass it through to the router so the system-prompt variant and
    the optional `hint` field are wired up. The selection itself runs
    in `app.services.checkpoint_selector.select_checkpoint_mode`.
    """
    # 0. Load custom profile settings if authenticated
    custom_settings = None
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization[7:]
            from app.dependencies import get_profile_settings
            from app.routers.auth import get_profile_id
            profile_id = await get_profile_id(token)
            if profile_id:
                custom_settings = await get_profile_settings(profile_id)
        except Exception:
            pass

    # 0a. T1-C: pick the mode. When the client supplies an explicit
    # `checkpoint_mode` we honour it (subject to the `override_mode`
    # escape hatch); otherwise we let the selector choose based on
    # the student's recent review history.
    chosen_mode = req.checkpoint_mode
    selection_rationale = "client_provided"
    if not chosen_mode or (not req.override_mode and chosen_mode not in {"direct", "scaffolded", "contrastive"}):
        chosen_mode = None  # let the selector fall back to direct

    if chosen_mode is None:
        try:
            from app.services.checkpoint_selector import (
                select_checkpoint_mode,
                CheckpointMode,
            )
            recent_events: list[dict] = []
            if authorization and authorization.startswith("Bearer "):
                recent_events = await _fetch_recent_concept_reviews(
                    token=authorization[7:],
                    concept_tag=req.concept_tag,
                )
            sel = select_checkpoint_mode(
                concept_tag=req.concept_tag,
                recent_review_events=recent_events,
            )
            chosen_mode = sel.mode.value
            selection_rationale = sel.rationale
        except Exception as e:
            logger.warning("checkpoint_selector_failed", extra={"error": str(e)})
            chosen_mode = "direct"
            selection_rationale = "selector_error_fallback"

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
        checkpoint_mode=chosen_mode,
        **kwargs
    )

    tag = diagnosis.get("tag", "general_logic_error")
    explanation = diagnosis.get("explanation", "Logic mismatch detected.")

    # 1b. T1-C: log the chosen mode into llm_call_metrics so the
    # methodology contribution can slice by adaptation arm. Fire-and-
    # forget: the helper itself swallows errors.
    try:
        user_uuid: str | None = None
        if authorization and authorization.startswith("Bearer "):
            user = await get_current_user(authorization)
            user_uuid = user.get("id") if user else None
        await _log_checkpoint_mode_metric(
            mode=chosen_mode,
            tag=tag,
            trace_id=req.trace_id,
            user_id=user_uuid,
        )
    except Exception:  # pragma: no cover — already logged inside helper
        pass

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
        "checkpoint_mode": chosen_mode,
        "checkpoint_mode_rationale": selection_rationale,
        # The hint is a feature of the *adaptive* modes; in DIRECT the
        # student doesn't get a scaffolding nudge, so we drop the field
        # entirely. The frontend uses field-presence to decide whether
        # to render the "Show hint" affordance.
        "hint": diagnosis.get("hint") if chosen_mode in {"scaffolded", "contrastive"} else None,
    }


async def _log_checkpoint_mode_metric(
    *,
    mode: str,
    tag: str,
    trace_id: str | None,
    user_id: str | None,
) -> None:
    """Best-effort insert a single ``llm_call_metrics`` row tagged with the
    adaptive-difficulty mode (T1-C). Mirrors the pattern in
    ``llm_ab._log_ablation_metrics`` — service-role write so anonymous
    traffic still gets logged, and failures are swallowed because the
    metric is observational, not blocking.
    """
    if not settings.supabase_url or not settings.supabase_service_key:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.supabase_url}/rest/v1/llm_call_metrics",
                headers={
                    "apikey": settings.supabase_service_key,
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json=[
                    {
                        "cache_key": f"diagnose:{tag}:{mode}",
                        "model_used": "diagnose_router",
                        "model_name": "diagnose_router",
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "latency_ms": 0,
                        "cache_hit": False,
                        "checkpoint_mode": mode,
                        "user_id": user_id,
                    }
                ],
            )
    except Exception as e:  # pragma: no cover — defensive
        logger.debug("checkpoint_mode_metric_failed", extra={"error": str(e)})


async def _fetch_recent_concept_reviews(
    *,
    token: str,
    concept_tag: str | None,
    lookback_days: int = 30,
    limit: int = 100,
) -> list[dict]:
    """Fetch the caller's recent review_events for a single concept.

    Used by the T1-C checkpoint selector. Soft-fails on any error — the
    selector itself returns DIRECT in that case. We never raise to the
    caller: a missing review history is the empty case, not an error.
    """
    if not concept_tag:
        return []
    try:
        from datetime import UTC, datetime, timedelta

        from app.config import settings

        cutoff = (datetime.now(UTC) - timedelta(days=lookback_days)).isoformat()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/review_events",
                params={
                    "select": "concept_tag,rating,occurred_at",
                    "concept_tag": f"eq.{concept_tag}",
                    "occurred_at": f"gte.{cutoff}",
                    "order": "occurred_at.desc",
                    "limit": str(limit),
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": settings.supabase_service_key,
                },
            )
        if resp.status_code == 200:
            return resp.json() or []
    except Exception as e:  # pragma: no cover — defensive
        logger.debug("recent_concept_reviews_fetch_failed", extra={"error": str(e)})
    return []

