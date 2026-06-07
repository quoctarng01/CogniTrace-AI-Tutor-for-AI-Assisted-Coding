# File: backend/app/routers/examples.py
# Follow this EXACTLY. Do not rename, skip, or modify any variable names.

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Header, Query, Request
from pydantic import BaseModel, Field

from app.config import Settings, settings
from app.routers.auth import get_current_user, get_profile_id

logger = logging.getLogger("codescope.examples")
router = APIRouter()

# ── Rate Limiter ────────────────────────────────────────────────
# Both GET and POST endpoints are rate-limited via slowapi.
# slowapi must be installed: pip install slowapi

_limiter = None
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    _limiter = Limiter(key_func=get_remote_address)
except ImportError:
    pass  # slowapi not installed — rate limiting disabled


def _rate_limit(rate: str):
    """Decorator factory for rate limiting. Returns a no-op decorator if slowapi is unavailable."""
    def decorator(func):
        if _limiter is None:
            return func
        return _limiter.limit(rate)(func)
    return decorator


# ── Pydantic Models ────────────────────────────────────────────

class Annotation(BaseModel):
    """One annotation attached to a specific line in the code snippet."""
    line: int = Field(..., ge=1, description="1-indexed line number in the code")
    text: str = Field(..., description="Plain-text explanation of what happens on this line")
    type: str = Field(
        ...,
        description=(
            "Type of annotation. Allowed values: scope | filter | iterator | guard | "
            "assignment | function_call | passthrough | side_effect | async_cm | "
            "executor | offload | yield | body | cleanup | metadata_preservation | "
            "enforcement | validation | rollback | commit | begin | nonlocal | mutation | "
            "partial | factory | typevar | parameterized | generic_class | callable_sig | "
            "nested_call | coalesce | ternary | sentinel | default | config_layer | "
            "func_layer | execution_layer | init | callable_layer | abc | contract | "
            "boilerplate | mutable_default | mixin | mixin_usage | self_reflection | "
            "enter | exit | timing | async_wait | closure_var | dedup | range_check"
        ),
    )


class ExampleRecord(BaseModel):
    """Response model for a single example record."""
    model_config = {"extra": "ignore"}

    id: str
    category: str
    title: str
    code: str
    why_ai_generates_this: Optional[str] = None
    annotations: list[Annotation] = []
    explanation: str
    common_mistakes: list[str] = []
    review_interval: str = "1,3,7"


class ExampleListResponse(BaseModel):
    examples: list[ExampleRecord]
    total: int
    limit: int
    offset: int


class SaveExampleRequest(BaseModel):
    """Optional body for POST /examples/{id}/save. Currently unused but reserved for future notes field."""
    model_config = {"extra": "ignore"}
    notes: Optional[str] = None


class SaveExampleResponse(BaseModel):
    card_id: str
    message: str
    existing: bool = False


# ── Internal Helpers ─────────────────────────────────────────────

def _parse_annotations(raw) -> list[Annotation]:
    """Parse the JSONB annotations column from Supabase into a list of Annotation objects."""
    import json
    if isinstance(raw, str):
        if not raw.strip():
            return []
        raw = json.loads(raw)
    if not raw:
        return []
    return [Annotation(**a) for a in raw]


async def _fetch_profile(authorization: str, user_id: str) -> dict:
    """Fetch the user's profile from Supabase to check their plan."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            params={"user_id": f"eq.{user_id}", "select": "*", "limit": "1"},
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
            },
        )
    if resp.status_code == 200:
        rows = resp.json()
        return rows[0] if rows else {}
    return {}


async def _check_existing_card(
    settings: Settings,
    authorization: str,
    user_id: str,
    profile_id: str,
    example_id: str,
) -> Optional[str]:
    """
    Check if the user already has a review_card for this example.
    Matches by profile_id (user) + concept_tag matching the example category prefix.
    Returns the existing card_id if found, otherwise None.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/review_cards",
            params={
                "user_id": f"eq.{profile_id}",
                "concept_tag": f"like.%{example_id[:8]}%",  # prefix match on concept_tag
                "select": "id",
                "limit": "1",
            },
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
            },
        )
    if resp.status_code == 200:
        rows = resp.json()
        if rows:
            return str(rows[0]["id"])
    return None


async def _get_or_create_trace(
    settings: Settings,
    authorization: str,
    user_id: str,
    profile_id: str,
    example: ExampleRecord,
) -> str:
    """Create a minimal trace row in Supabase for this example. Returns the trace_id."""
    import json
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/traces",
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json={
                "user_id": profile_id,
                "code": example.code,
                "language": "python",
                "steps": json.dumps([]),
                "concept_tags": [example.category],
                "is_public": False,
            },
        )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="Failed to create trace for example")
    data = resp.json()
    return str(data[0]["id"]) if isinstance(data, list) else str(data.get("id", ""))


async def _create_review_card(
    settings: Settings,
    authorization: str,
    profile_id: str,
    trace_id: str,
    example: ExampleRecord,
) -> str:
    """Create a review_card with SM-2 initial values. Returns the card_id."""
    intervals = [s.strip() for s in example.review_interval.split(",") if s.strip()]
    first_interval = int(intervals[0]) if intervals else 1
    next_review = (date.today() + timedelta(days=first_interval)).isoformat()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/review_cards",
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json={
                "user_id": profile_id,
                "trace_id": trace_id,
                "concept_tag": example.category,
                "easiness_factor": 2.5,
                "interval_days": first_interval,
                "repetitions": 0,
                "next_review_date": next_review,
            },
        )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="Failed to create review card")
    data = resp.json()
    return str(data[0]["id"]) if isinstance(data, list) else str(data.get("id", ""))


# ── Endpoints ───────────────────────────────────────────────────

@_rate_limit("60/minute")
@router.get("/", response_model=ExampleListResponse)
async def list_examples(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=50, description="Results per page"),
    offset: int = Query(0, ge=0, description="Skip N results"),
):
    """
    List all examples, optionally filtered by category.
    Public: no authentication required.
    Rate limit: 60 requests/minute per IP.
    """

    # Build main query params (fetches limited rows for display)
    params: dict[str, str] = {
        "select": "*",
        "limit": str(limit),
        "offset": str(offset),
        "order": "created_at.asc",
    }
    # Build count query params (minimal select, just for total count)
    count_params: dict[str, str] = {"select": "id"}

    if category:
        params["category"] = f"eq.{category}"
        count_params["category"] = f"eq.{category}"

    headers = {"apikey": settings.supabase_service_key}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/examples",
            params=params,
            headers=headers,
        )

    if resp.status_code != 200:
        logger.error("Failed to fetch examples: %s", resp.text)
        raise HTTPException(status_code=502, detail="Failed to fetch examples from database")

    rows = resp.json() or []

    examples = [
        ExampleRecord(
            id=str(row["id"]),
            category=row.get("category", ""),
            title=row.get("title", ""),
            code=row.get("code", ""),
            why_ai_generates_this=row.get("why_ai_generates_this"),
            annotations=_parse_annotations(row.get("annotations")),
            explanation=row.get("explanation", ""),
            common_mistakes=row.get("common_mistakes") or [],
            review_interval=row.get("review_interval", "1,3,7"),
        )
        for row in rows
    ]

    # Fetch total count using Supabase content-range header
    async with httpx.AsyncClient(timeout=10.0) as client:
        count_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/examples",
            params=count_params,
            headers={**headers, "Prefer": "count=exact"},
        )

    total = 0
    if count_resp.status_code == 200:
        content_range = count_resp.headers.get("content-range", "")
        if "/" in content_range:
            try:
                total = int(content_range.split("/")[-1])
            except ValueError:
                total = len(rows)  # fallback to returned row count

    return ExampleListResponse(examples=examples, total=total, limit=limit, offset=offset)


@_rate_limit("60/minute")
@router.get("/{example_id}", response_model=ExampleRecord)
async def get_example(request: Request, example_id: str):
    """
    Get a single example by ID, including all annotations.
    Public: no authentication required.
    Rate limit: 60 requests/minute per IP.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/examples",
            params={"id": f"eq.{example_id}", "select": "*", "limit": "1"},
            headers={"apikey": settings.supabase_service_key},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch example")

    rows = resp.json() or []
    if not rows:
        raise HTTPException(status_code=404, detail="Example not found")

    row = rows[0]
    return ExampleRecord(
        id=str(row["id"]),
        category=row.get("category", ""),
        title=row.get("title", ""),
        code=row.get("code", ""),
        why_ai_generates_this=row.get("why_ai_generates_this"),
        annotations=_parse_annotations(row.get("annotations")),
        explanation=row.get("explanation", ""),
        common_mistakes=row.get("common_mistakes") or [],
            review_interval=row.get("review_interval", "1,3,7"),
    )


@_rate_limit("10/minute")
@router.post("/{example_id}/save", response_model=SaveExampleResponse)
async def save_example_to_queue(
    example_id: str,
    req: Optional[SaveExampleRequest] = None,
    authorization: str = Header(None),
    request: Request = None,
):
    """
    Add an example to the authenticated user's review queue.
    Auth: Required (Pro plan only).
    Deduplication: Returns 200 with existing card_id if already saved.
    Status codes: 201 (new), 200 (existing), 401 (no auth), 403 (free plan), 404 (example not found).
    Rate limit: 10 requests/minute per IP.
    """
    # ── Auth check ─────────────────────────────────────────────
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(authorization)
    user_id = user.get("id", "")

    # ── Pro plan check ─────────────────────────────────────────
    profile = await _fetch_profile(authorization, user_id)
    if profile.get("plan") != "pro":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "UPGRADE_REQUIRED",
                "message": "This feature requires a Pro subscription.",
                "upgrade_url": "/upgrade",
            },
        )

    profile_id = await get_profile_id(authorization[7:] if authorization else None)
    if not profile_id:
        raise HTTPException(status_code=404, detail="Profile not found for user")

    # ── Fetch the example ──────────────────────────────────────
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/examples",
            params={"id": f"eq.{example_id}", "select": "*", "limit": "1"},
            headers={"apikey": settings.supabase_service_key},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch example")

    rows = resp.json() or []
    if not rows:
        raise HTTPException(status_code=404, detail="Example not found")

    row = rows[0]
    example = ExampleRecord(
        id=str(row["id"]),
        category=row.get("category", ""),
        title=row.get("title", ""),
        code=row.get("code", ""),
        why_ai_generates_this=row.get("why_ai_generates_this"),
        annotations=_parse_annotations(row.get("annotations")),
        explanation=row.get("explanation", ""),
        common_mistakes=row.get("common_mistakes") or [],
            review_interval=row.get("review_interval", "1,3,7"),
    )

    # ── Deduplication check ─────────────────────────────────────
    existing_card_id = await _check_existing_card(
        settings, authorization, user_id, profile_id, example_id
    )
    if existing_card_id:
        return SaveExampleResponse(
            card_id=existing_card_id,
            message="Already in your review queue",
            existing=True,
        )

    # ── Create trace + review_card ───────────────────────────────
    trace_id = await _get_or_create_trace(
        settings, authorization, user_id, profile_id, example
    )
    card_id = await _create_review_card(
        settings, authorization, profile_id, trace_id, example
    )

    logger.info(
        "example_saved",
        extra={
            "card_id": card_id,
            "example_id": example_id,
            "user_id": user_id,
        },
    )

    intervals = [s.strip() for s in example.review_interval.split(",") if s.strip()]
    first_interval = int(intervals[0]) if intervals else 1

    return SaveExampleResponse(
        card_id=card_id,
        message=f"Added '{example.title}' to your review queue. First review in {first_interval} day(s).",
        existing=False,
    )
