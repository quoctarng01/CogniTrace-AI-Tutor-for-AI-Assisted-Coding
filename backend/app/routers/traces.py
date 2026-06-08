"""Trace execution API endpoints."""
import ast
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field
import httpx
import secrets
import logging
import bcrypt

from datetime import date, datetime
from tracer.validator import validate_code
from tracer.runner import run_trace as run_trace_subprocess
from app.config import settings
from app.routers.auth import get_current_user
from app.routers.review import _calculate_streak
from app.dependencies import get_profile_id_for_user, is_pro_user, get_http_client
from fastapi import Depends
from typing import Annotated

logger = logging.getLogger("codescope.traces")

# ── Rate Limiter ────────────────────────────────────────────────
_limiter = None
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    _limiter = Limiter(key_func=get_remote_address)
except ImportError:
    pass  # slowapi not installed — rate limiting disabled


# ── Helper Functions ────────────────────────────────────────────────


async def _get_trace_count_this_month(user_id: str, settings_obj, client: httpx.AsyncClient | None = None) -> int:
    """Count traces created by user in the current calendar month."""
    now = datetime.utcnow()
    month_start = f"{now.year}-{now.month:02d}-01"
    
    if client is not None:
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
    else:
        async with httpx.AsyncClient(timeout=10.0) as temp_client:
            resp = await temp_client.get(
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
    initial_namespace: dict[str, str] | None = Field(
        default=None,
        description=(
            "Optional initial variable values as name→string pairs. "
            "Values are evaluated as Python literals. "
            "Example: {\"items\": \"[1, 2, 3]\", \"threshold\": \"10\"}"
        ),
    )


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
    checkpoints: list[dict] = []


def _rate_limit(rate: str):
    """Decorator factory for rate limiting."""
    def decorator(func):
        if _limiter is None:
            return func
        return _limiter.limit(rate)(func)
    return decorator


def rate_limit_dependency(rate: str):
    """Dependency for rate limiting."""
    if _limiter is None:
        return None
    return _limiter.limit(rate)


@router.post("/traces/run", response_model=TraceResponse)
@_rate_limit("30/minute")
async def run_trace(
    req: TraceRequest,
    authorization: str = Header(None),
    request: Request = None,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """
    Execute Python code and return a step-by-step trace.
    Side-effect patterns (import os, eval, open(), etc.) are blocked.
    print() is allowed but warned about.
    Free users are limited to 50 traces per month; Pro users have unlimited.
    """
    # Step 0: Check rate limit for non-Pro users
    if authorization:
        user = await get_current_user(request, authorization)
        user_id = user.get("id", "")
        
        # Check if user is Pro
        is_pro = await is_pro_user(user_id, client)
        
        if not is_pro:
            # Count user's traces this month
            FREE_TRACE_LIMIT = 50
            trace_count = await _get_trace_count_this_month(user_id, settings, client)
            
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

    # Step 2: Parse initial_namespace values from strings to Python values
    initial_ns = None
    if req.initial_namespace:
        initial_ns = {}
        for name, val_str in req.initial_namespace.items():
            try:
                initial_ns[name] = ast.literal_eval(val_str)
            except (ValueError, SyntaxError):
                pass  # Skip invalid values

    # Step 3: Run the tracer in a subprocess (offloaded to thread pool)
    from app.concurrency import run_with_concurrency_limit
    result = await run_with_concurrency_limit(
        lambda: run_trace_subprocess(req.code, max_steps=500, initial_namespace=initial_ns)
    )

    # Step 4: Handle errors
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
        checkpoints=result.get("checkpoints", []),
    )


# ── Dashboard ──────────────────────────────────────────────────────

class DashboardResponse(BaseModel):
    traces: list
    due_cards: list
    streak: int
    total_traces: int


@router.get("/dashboard")
async def get_dashboard(
    request: Request,
    authorization: str = Header(None),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """Aggregated dashboard: traces + due cards + streak. Single call for the frontend."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(request, authorization)
    user_id = user.get("id", "")

    # Map user UUID (auth.users.id) to profile_id (profiles.id)
    profile_id = await get_profile_id_for_user(user_id, client)

    if not profile_id:
        return DashboardResponse(
            traces=[],
            due_cards=[],
            streak=int(0),
            total_traces=0,
        )

    headers = {
        "Authorization": f"Bearer {authorization[7:]}",
        "apikey": settings.supabase_service_key,
    }

    traces_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"user_id": f"eq.{profile_id}", "select": "*", "order": "created_at.desc", "limit": "20"},
        headers=headers,
    )
    traces = traces_resp.json() if traces_resp.status_code == 200 else []

    # Fetch true total count (separate query, no limit)
    count_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"user_id": f"eq.{profile_id}", "select": "id"},
        headers={**headers, "Prefer": "count=exact"},
    )
    total_traces_count = len(traces)  # default to page count
    if count_resp.status_code == 200:
        content_range = count_resp.headers.get("content-range", "")
        if "/" in content_range:
            try:
                total_traces_count = int(content_range.split("/")[-1])
            except ValueError:
                pass

    today = date.today().isoformat()
    cards_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/review_cards",
        params={"user_id": f"eq.{profile_id}", "next_review_date": f"lte.{today}", "select": "*"},
        headers=headers,
    )
    due_cards = cards_resp.json() if cards_resp.status_code == 200 else []

    # Calculate streak using the profile_id
    streak = await _calculate_streak(profile_id, settings.supabase_url, settings.supabase_service_key, client)

    return DashboardResponse(
        traces=traces,
        due_cards=[{**c, "due": True} for c in due_cards],
        streak=streak,
        total_traces=total_traces_count,
    )


# ── Save / List / Share Endpoints ───────────────────────────────

class SaveTraceRequest(BaseModel):
    code: str
    language: str = "python"
    steps: list[dict] = Field(
        default_factory=list,
        description="Full trace steps array for replay. Stored in DB so saved traces can be replayed without re-execution.",
    )
    concept_tags: list[str] = []
    is_public: bool = False


class ShareTraceRequest(BaseModel):
    """Request body for POST /traces/{id}/share."""
    expiration_days: int | None = Field(
        default=None,
        ge=0,
        le=365,
        description="Days until link expires. null/0 = never.",
    )
    password: str | None = Field(
        default=None,
        max_length=128,
        description="Optional password to protect the shared link.",
    )


class ForkTraceResponse(BaseModel):
    trace_id: str
    share_token: str
    share_url: str


@router.post("/traces", response_model=dict)
async def save_trace(
    req: SaveTraceRequest,
    request: Request,
    authorization: str = Header(None),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """Save a trace. Auth required."""
    logger.info("save_trace_called", extra={"location": "traces.py:save_trace", "has_auth": authorization is not None})
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(request, authorization)
    user_id = user.get("id", "")
    logger.info("save_trace_user", extra={"user_id": user_id})

    # Re-validate code before saving
    is_valid, blocking, _ = validate_code(req.code)
    if not is_valid:
        raise HTTPException(status_code=422, detail={
            "error": "SIDE_EFFECT_BLOCKED",
            "matched": [e["pattern"] for e in blocking],
        })

    # Look up profiles.id where profiles.user_id = user_id (auth UUID)
    profile_id = await get_profile_id_for_user(user_id, client)

    if not profile_id:
        raise HTTPException(status_code=404, detail="User profile not found")

    share_token = secrets.token_hex(16)

    # Only send columns that actually exist in the Supabase traces table
    trace_data = {
        "user_id": profile_id,
        "code": req.code,
        "language": req.language if req.language else "python",
        "concept_tags": req.concept_tags if req.concept_tags else [],
        "is_public": req.is_public if req.is_public is not None else False,
        "share_token": share_token,
        "steps": req.steps if req.steps else [],  # ← SAVE FULL STEPS for replay
    }

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
    request: Request,
    authorization: str = Header(None),
    limit: int = 20,
    offset: int = 0,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """List user's saved traces. Auth required."""
    logger.info("list_traces_called", extra={"location": "traces.py:list_traces", "has_auth": authorization is not None})
    
    if not authorization:
        logger.warning("list_traces_no_auth")
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        user = await get_current_user(request, authorization)
        user_id = user.get("id", "")
        logger.info("list_traces_got_user", extra={"user_id": user_id})
    except HTTPException as e:
        logger.warning("list_traces_auth_failed", extra={"detail": str(e.detail)})
        raise
 
    # Map user UUID (auth.users.id) to profile_id (profiles.id)
    profile_id = await get_profile_id_for_user(user_id, client)
 
    if not profile_id:
        return {"traces": [], "total_traces": 0}
 
    logger.debug("list_traces_settings_loaded", extra={"supabase_url": settings.supabase_url})
     
    # Fetch the page of traces
    resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={
            "user_id": f"eq.{profile_id}",
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

    # Fetch the true total count (no limit, ask Supabase for exact count)
    count_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"user_id": f"eq.{profile_id}", "select": "id"},
        headers={
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
            "Prefer": "count=exact",
        },
    )

    traces = resp.json() if resp.status_code == 200 else []

    # Parse true total from the Content-Range header (e.g. "0-19/347")
    total_traces_count = len(traces)  # safe fallback
    if count_resp.status_code == 200:
        content_range = count_resp.headers.get("content-range", "")
        if "/" in content_range:
            try:
                total_traces_count = int(content_range.split("/")[-1])
            except ValueError:
                pass

    logger.info("list_traces_returning", extra={"trace_count": len(traces), "total": total_traces_count})
    return {"traces": traces, "total_traces": total_traces_count}


@router.get("/traces/shared/{share_token}")
async def get_shared_trace(
    share_token: str,
    authorization: str | None = Header(None),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """
    Fetch a trace by share_token.

    If authenticated (owner), returns the trace if:
      - is_public=true  OR
      - user_id matches the authenticated user's profile

    If anonymous, returns only is_public=true traces.
    """
    from app.routers.auth import get_profile_id

    owner_id = None
    if authorization:
        token = authorization.replace("Bearer ", "")
        owner_id = await get_profile_id(token, client)

    if owner_id:
        params = {
            "share_token": f"eq.{share_token}",
            "or": f"(is_public.eq.true,user_id.eq.{owner_id})",
            "select": "*",
            "limit": "1",
        }
        headers = {
            "apikey": settings.supabase_service_key,
            "Authorization": f"Bearer {settings.supabase_service_key}",
        }
    else:
        params = {
            "share_token": f"eq.{share_token}",
            "is_public": "eq.true",
            "select": "*",
            "limit": "1",
        }
        headers = {
            "apikey": settings.supabase_service_key,
            "Authorization": f"Bearer {settings.supabase_service_key}",
        }

    resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params=params,
        headers=headers,
    )

    if resp.status_code != 200 or not resp.json():
        raise HTTPException(status_code=404, detail="Trace not found")

    trace = resp.json()[0]

    # Check expiration
    expires_at = trace.get("expires_at")
    if expires_at:
        from datetime import datetime, timezone
        try:
            exp_date = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp_date:
                raise HTTPException(
                    status_code=410,
                    detail={
                        "error": "EXPIRED",
                        "message": "This trace has expired. Sign in to CogniTrace to view it.",
                        "login_url": "/auth/login",
                    },
                )
        except ValueError:
            pass  # Invalid date format — treat as not expired

    # Return trace data (exclude password_hash from client response)
    result = {k: v for k, v in trace.items() if k != "password_hash"}
    return result


@router.post("/traces/shared/{share_token}/fork")
async def fork_shared_trace(
    share_token: str,
    request: Request,
    authorization: str = Header(None),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """
    Fork a shared trace — copies it into the authenticated user's account.
    The fork is a NEW trace owned by the caller, independent of the original.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(request, authorization)
    user_id = user.get("id", "")

    # Map user UUID (auth.users.id) to profile_id (profiles.id)
    profile_id = await get_profile_id_for_user(user_id, client)

    if not profile_id:
        raise HTTPException(status_code=404, detail="User profile not found")

    # Get the original trace
    orig_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"share_token": f"eq.{share_token}", "select": "*"},
        headers={"apikey": settings.supabase_service_key},
    )

    orig_traces = orig_resp.json() if orig_resp.status_code == 200 else []
    if not orig_traces:
        raise HTTPException(status_code=404, detail="Shared trace not found")

    orig = orig_traces[0]

    # Create fork — new profile_id, new share_token, same code + steps
    new_share_token = secrets.token_hex(16)
    fork_data = {
        "user_id": profile_id,
        "code": orig.get("code", ""),
        "language": orig.get("language", "python"),
        "concept_tags": orig.get("concept_tags", []),
        "is_public": False,
        "share_token": new_share_token,
        "steps": orig.get("steps"),
    }

    fork_resp = await client.post(
        f"{settings.supabase_url}/rest/v1/traces",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_key}",
            "apikey": settings.supabase_service_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json=fork_data,
    )

    if fork_resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="Failed to fork trace")

    fork = fork_resp.json()
    if isinstance(fork, list) and len(fork) > 0:
        fork = fork[0]

    logger.info("trace_forked", extra={
        "original_token": share_token,
        "new_trace_id": fork.get("id", ""),
        "user_id": user_id,
    })

    return ForkTraceResponse(
        trace_id=fork.get("id", ""),
        share_token=new_share_token,
        share_url=f"/trace/{new_share_token}",
    )


@router.post("/traces/{trace_id}/share")
async def share_trace(
    trace_id: str,
    request: Request,
    req: ShareTraceRequest | None = None,
    authorization: str = Header(None),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """
    Generate or update a share link for a trace.
    Sets is_public=true and generates a new share_token.

    Body (optional):
      - expiration_days: int | null — days until expiry (null/0 = never)
      - password: str | null — optional protection password
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    share_token = secrets.token_hex(16)

    # Build update payload
    update_payload: dict = {
        "share_token": share_token,
        "is_public": True,
    }

    # Handle expiration
    if req and req.expiration_days and req.expiration_days > 0:
        from datetime import datetime, timedelta, timezone
        expires = datetime.now(timezone.utc) + timedelta(days=req.expiration_days)
        update_payload["expires_at"] = expires.isoformat()
    else:
        update_payload["expires_at"] = None

    # Handle password protection
    if req and req.password:
        hashed = bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        update_payload["password_hash"] = hashed
    else:
        update_payload["password_hash"] = None

    # Verify the trace belongs to this user first
    user = await get_current_user(request, authorization)
    user_id = user.get("id", "")

    # Map user UUID (auth.users.id) to profile_id (profiles.id)
    profile_id = await get_profile_id_for_user(user_id, client)

    if not profile_id:
        raise HTTPException(status_code=404, detail="User profile not found")

    check_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"id": f"eq.{trace_id}", "user_id": f"eq.{profile_id}", "select": "id"},
        headers={
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
        },
    )
    if check_resp.status_code != 200 or not check_resp.json():
        raise HTTPException(status_code=404, detail="Trace not found")

    resp = await client.patch(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"id": f"eq.{trace_id}"},
        headers={
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json=update_payload,
    )

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Trace not found")

    return {
        "share_token": share_token,
        "share_url": f"/trace/{share_token}",
        "expires_at": update_payload.get("expires_at"),
        "has_password": bool(req and req.password),
    }
