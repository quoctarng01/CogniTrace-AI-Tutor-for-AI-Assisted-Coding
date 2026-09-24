"""Trace persistence endpoints (Workstream 2: split from monolithic traces.py).

This router owns:
    - POST /api/traces              — save a trace
    - GET  /api/traces              — list the current user's traces

Other trace-related concerns live in:
    - `traces.py` — run, fork (the execution surface)
    - `traces_share.py` — share links, shared-trace fetch and fork
    - `dashboard.py` — aggregated dashboard widget
"""
from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, Header, Request
from httpx import AsyncClient
from pydantic import BaseModel, Field

from app.config import settings
from app.dependencies import get_http_client, get_profile_id_for_user
from app.rate_limit_decorator import _rate_limit
from app.routers.auth import get_current_user
from app.services.errors import (
    auth_required_401,
    profile_not_found_404,
    side_effect_blocked_422,
    upstream_failure_502,
)
from tracer.validator import validate_code

logger = logging.getLogger("cognitrace.traces_save")

router = APIRouter()


class SaveTraceRequest(BaseModel):
    code: str = Field(..., max_length=5000)
    language: str = "python"
    steps: list[dict] = Field(default_factory=list)
    concept_tags: list[str] = []
    is_public: bool = False


@router.post("/traces")
@_rate_limit("20/minute")
async def save_trace(
    req: SaveTraceRequest,
    request: Request,
    authorization: str | None = Header(None),
    client: AsyncClient = Depends(get_http_client),
):
    """Persist a trace so it can be replayed without re-executing the code.

    Re-runs the validator before saving (the trace may have been executed before
    a tighter validator rule was added).
    """
    if not authorization:
        raise auth_required_401()

    user = await get_current_user(request, authorization)
    user_id = user.get("id", "")
    profile_id = await get_profile_id_for_user(user_id, client)
    if not profile_id:
        raise profile_not_found_404()

    is_valid, blocking, _ = validate_code(req.code)
    if not is_valid:
        raise side_effect_blocked_422([b["pattern"] for b in blocking])

    share_token = secrets.token_hex(16)
    payload = {
        "user_id": profile_id,
        "code": req.code,
        "language": req.language or "python",
        "concept_tags": req.concept_tags or [],
        "is_public": bool(req.is_public),
        "share_token": share_token,
        "steps": req.steps or [],
    }

    resp = await client.post(
        f"{settings.supabase_url}/rest/v1/traces",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_key}",
            "apikey": settings.supabase_service_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json=payload,
    )
    if resp.status_code not in (200, 201):
        raise upstream_failure_502(resp.text)

    data = resp.json()
    if isinstance(data, list) and data:
        data = data[0]
    trace_id = data.get("id", "")

    # Workstream 12: stamp the fingerprint on every save. This is best-effort —
    # a fingerprint failure must not block the user from saving their trace.
    # We log and move on; the read endpoint will lazy-compute on first access
    # if this insert fails for any reason (network blip, migration not applied,
    # etc.).
    if trace_id:
        try:
            from app.services.fingerprint import compute_fingerprint

            fp = compute_fingerprint(req.code, req.steps or [])
            upsert = await client.post(
                f"{settings.supabase_url}/rest/v1/trace_fingerprints",
                json={
                    "trace_id": trace_id,
                    "user_id": profile_id,
                    "fingerprint_json": fp.to_dict(),
                    "compact": fp.compact(),
                    "short_form": fp.short(),
                    "signature": fp.signature(),
                    "branches": fp.branches,
                    "recursion_depth": fp.recursion_depth,
                    "loop_iterations": fp.loop_iterations,
                    "total_steps": fp.total_steps,
                    "conceptual_complexity": fp.conceptual_complexity,
                    "total_duration_ms": fp.total_duration_ms,
                    "exception_types": list(fp.exception_types),
                },
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "apikey": settings.supabase_service_key,
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates",
                },
            )
            if upsert.status_code >= 400:
                logger.warning(
                    "fingerprint_upsert_failed",
                    extra={"trace_id": trace_id, "status": upsert.status_code},
                )
        except Exception as e:
            # Never block save on fingerprint failure — read path is lazy.
            logger.warning(
                "fingerprint_upsert_exception",
                extra={"trace_id": trace_id, "error": str(e)},
            )

    return {
        "id": data.get("id", ""),
        "share_token": data.get("share_token", share_token),
        "created_at": data.get("created_at", ""),
    }


@router.get("/traces")
async def list_traces(
    request: Request,
    authorization: str | None = Header(None),
    limit: int = 20,
    offset: int = 0,
    client: AsyncClient = Depends(get_http_client),
):
    """List the current user's saved traces, newest first."""
    if not authorization:
        raise auth_required_401()

    user = await get_current_user(request, authorization)
    profile_id = await get_profile_id_for_user(user.get("id", ""), client)
    if not profile_id:
        return {"traces": [], "total_traces": 0}

    headers = {
        "Authorization": f"Bearer {authorization[7:]}",
        "apikey": settings.supabase_service_key,
    }

    page_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={
            "user_id": f"eq.{profile_id}",
            "select": "*",
            "limit": str(limit),
            "offset": str(offset),
            "order": "created_at.desc",
        },
        headers=headers,
    )
    count_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"user_id": f"eq.{profile_id}", "select": "id"},
        headers={**headers, "Prefer": "count=exact"},
    )

    traces = page_resp.json() if page_resp.status_code == 200 else []

    total = len(traces)  # fallback
    if count_resp.status_code == 200:
        content_range = count_resp.headers.get("content-range", "")
        if "/" in content_range:
            try:
                total = int(content_range.split("/")[-1])
            except ValueError:
                pass

    return {"traces": traces, "total_traces": total}
