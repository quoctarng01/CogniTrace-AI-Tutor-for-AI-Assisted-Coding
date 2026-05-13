"""Trace execution API endpoints."""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional
import httpx
import secrets
import json
import logging

from datetime import date, datetime
from tracer.validator import validate_code
from tracer.runner import run_trace as run_trace_subprocess
from app.config import Settings
from app.routers.auth import get_current_user
from app.routers.review import _calculate_streak

logger = logging.getLogger("codescope.traces")


# ── Helper Functions ────────────────────────────────────────────────

async def _is_pro_user_in_traces(user_id: str | None) -> bool:
    """
    Check if user is on Pro plan.
    INLINED here to avoid circular import with llm.py.
    Must stay in sync with _is_pro_user in app/routers/llm.py.
    """
    if not user_id:
        return False
    settings = Settings()
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


async def _get_trace_count_this_month(user_id: str, settings_obj) -> int:
    """Count traces created by user in the current calendar month."""
    now = datetime.utcnow()
    month_start = f"{now.year}-{now.month:02d}-01"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings_obj.supabase_url}/rest/v1/traces",
            params={
                "user_id": f"eq.{user_id}",
                "created_at": f"gte.{month_start}",
                "select": "id",
            },
            headers={
                "Authorization": f"Bearer {settings_obj.supabase_service_key}",
                "apikey": settings_obj.supabase_service_key,
            },
        )
    
    if resp.status_code == 200:
        return len(resp.json())
    return 0

router = APIRouter()


class TraceRequest(BaseModel):
    """Request body for /api/traces/run."""
    code: str = Field(..., max_length=5000, description="Python source code to trace")


class VariableInfoResponse(BaseModel):
    """A variable's state in the response."""
    type: str
    value: str
    changed: bool


class TraceStepResponse(BaseModel):
    """One step in the trace response."""
    step_number: int
    line_number: int
    bytecode_offset: int
    opcode: str
    variables: dict[str, VariableInfoResponse]
    branches_taken: dict
    duration_ms: float


class TraceResponse(BaseModel):
    """Successful trace response."""
    steps: list[TraceStepResponse]
    total_steps: int
    duration_ms: float


@router.post("/traces/run", response_model=TraceResponse)
async def run_trace(req: TraceRequest, authorization: str = Header(None)):
    """
    Execute Python code and return a step-by-step trace.
    Side-effect patterns (import os, eval, open(), etc.) are blocked.
    print() is allowed but warned about.
    Free users are limited to 50 traces per month; Pro users have unlimited.
    """
    # Step 0: Check rate limit for non-Pro users
    if authorization:
        user = await get_current_user(authorization)
        user_id = user.get("id", "")
        
        # Check if user is Pro
        is_pro = await _is_pro_user_in_traces(user_id)
        
        if not is_pro:
            # Count user's traces this month
            FREE_TRACE_LIMIT = 50
            settings = Settings()
            trace_count = await _get_trace_count_this_month(user_id, settings)
            
            if trace_count >= FREE_TRACE_LIMIT:
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "FREE_LIMIT_REACHED",
                        "message": f"You've used your {FREE_TRACE_LIMIT} free traces this month. Upgrade to Pro for unlimited.",
                        "upgrade_url": "/upgrade",
                        "current_count": trace_count,
                        "limit": FREE_TRACE_LIMIT,
                    }
                )
    
    # Step 1: Validate for dangerous side effects
    is_valid, blocking_effects, warnings = validate_code(req.code)
    if not is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "SIDE_EFFECT_BLOCKED",
                "message": "This code contains patterns that are not allowed for security reasons.",
                "matched": [e["pattern"] for e in blocking_effects],
                "warnings": [w["pattern"] for w in warnings],
            }
        )

    # Step 2: Run the tracer in a subprocess
    result = run_trace_subprocess(req.code, max_steps=500)

    # Step 3: Handle errors
    if "error" in result:
        error_code = result["error"]
        if error_code == "TIMEOUT":
            raise HTTPException(
                status_code=408,
                detail={
                    "error": "TIMEOUT",
                    "message": result["message"],
                }
            )
        elif error_code == "SYNTAX_ERROR":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "SYNTAX_ERROR",
                    "message": result["message"],
                    "line": result.get("line"),
                }
            )
        elif error_code == "MAX_STEPS":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "MAX_STEPS",
                    "message": result["message"],
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": error_code,
                    "message": result.get("message", "Unknown error"),
                }
            )

    # Step 4: Return successful trace
    return TraceResponse(
        steps=[TraceStepResponse(**s) for s in result["steps"]],
        total_steps=result["total_steps"],
        duration_ms=result["duration_ms"],
    )


# ── Dashboard ──────────────────────────────────────────────────────

class DashboardResponse(BaseModel):
    traces: list
    due_cards: list
    streak: int
    total_traces: int


@router.get("/dashboard")
async def get_dashboard(authorization: str = Header(None)):
    """Aggregated dashboard: traces + due cards + streak. Single call for the frontend."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(authorization)
    user_id = user.get("id", "")
    settings = Settings()

    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
        }

        traces_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"user_id": f"eq.{user_id}", "select": "*", "order": "created_at.desc", "limit": "20"},
            headers=headers,
        )
        traces = traces_resp.json() if traces_resp.status_code == 200 else []

        today = date.today().isoformat()
        cards_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/review_cards",
            params={"user_id": f"eq.{user_id}", "next_review_date": f"lte.{today}", "select": "*"},
            headers=headers,
        )
        due_cards = cards_resp.json() if cards_resp.status_code == 200 else []

    # Calculate streak using the same function as review.py
    streak = await _calculate_streak(user_id, settings.supabase_url, settings.supabase_service_key)

    return DashboardResponse(
        traces=traces,
        due_cards=[{**c, "due": True} for c in due_cards],
        streak=streak,
        total_traces=len(traces),
    )


# ── Save / List / Share Endpoints ───────────────────────────────

class SaveTraceRequest(BaseModel):
    code: str
    language: str = "python"
    steps: list[dict] = []
    concept_tags: list[str] = []
    is_public: bool = False


@router.post("/traces", response_model=dict)
async def save_trace(
    req: SaveTraceRequest,
    authorization: str = Header(None),
):
    """Save a trace. Auth required."""
    logger.info("save_trace_called", extra={"location": "traces.py:save_trace", "has_auth": authorization is not None})
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(authorization)
    user_id = user.get("id", "")
    logger.info("save_trace_user", extra={"user_id": user_id})

    # Re-validate code before saving
    is_valid, blocking, _ = validate_code(req.code)
    if not is_valid:
        raise HTTPException(status_code=422, detail={
            "error": "SIDE_EFFECT_BLOCKED",
            "matched": [e["pattern"] for e in blocking],
        })

    settings = Settings()
    share_token = secrets.token_hex(16)

    # Only send columns that actually exist in the Supabase traces table
    trace_data = {
        "user_id": user_id,
        "code": req.code,
        "language": req.language if req.language else "python",
        "concept_tags": req.concept_tags if req.concept_tags else [],
        "is_public": req.is_public if req.is_public is not None else False,
        "share_token": share_token,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        logger.info("save_trace_supabase_call", extra={"url": settings.supabase_url})
        # Use service role key in Authorization to bypass RLS
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
        logger.info("save_trace_response", extra={"status_code": resp.status_code})

    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"Failed to save trace: {resp.text}")

    data = resp.json()
    if isinstance(data, list) and len(data) > 0:
        data = data[0]

    return {
        "id": data.get("id", ""),
        "share_token": data.get("share_token", share_token),
        "created_at": data.get("created_at", ""),
    }


@router.get("/traces")
async def list_traces(
    authorization: str = Header(None),
    limit: int = 20,
    offset: int = 0,
):
    """List user's saved traces. Auth required."""
    logger.info("list_traces_called", extra={"location": "traces.py:list_traces", "has_auth": authorization is not None})
    
    if not authorization:
        logger.warning("list_traces_no_auth")
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        user = await get_current_user(authorization)
        user_id = user.get("id", "")
        logger.info("list_traces_got_user", extra={"user_id": user_id})
    except HTTPException as e:
        logger.warning("list_traces_auth_failed", extra={"detail": str(e.detail)})
        raise

    settings = Settings()
    logger.debug("list_traces_settings_loaded", extra={"supabase_url": settings.supabase_url})
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={
                "user_id": f"eq.{user_id}",
                "select": "*",
                "limit": str(limit),
                "offset": str(offset),
                "order": "created_at.desc",
            },
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
            },
        )
        logger.info("list_traces_response", extra={"status_code": resp.status_code})

    traces = resp.json() if resp.status_code == 200 else []
    logger.info("list_traces_returning", extra={"trace_count": len(traces)})
    return {"traces": traces, "total_traces": len(traces)}


@router.get("/traces/shared/{share_token}")
async def get_shared_trace(share_token: str):
    """Get a trace by its share token. Public endpoint."""
    settings = Settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={
                "share_token": f"eq.{share_token}",
                "is_public": "eq.true",
                "select": "*",
            },
            headers={"apikey": settings.supabase_service_key},
        )

    traces = resp.json() if resp.status_code == 200 else []
    if not traces:
        raise HTTPException(status_code=404, detail="Trace not found")
    return traces[0]


@router.post("/traces/{trace_id}/share")
async def share_trace(
    trace_id: str,
    authorization: str = Header(None),
):
    """Generate or update a share link for a trace."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    settings = Settings()
    share_token = secrets.token_hex(16)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.patch(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"id": f"eq.{trace_id}"},
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={"share_token": share_token, "is_public": True},
        )

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Trace not found")

    return {"share_token": share_token, "share_url": f"/trace/{share_token}"}
