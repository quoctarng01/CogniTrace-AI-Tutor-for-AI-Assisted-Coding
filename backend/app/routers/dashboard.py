"""Aggregated dashboard endpoint (Workstream 2: split from monolithic traces.py).

This router owns:
    - GET /api/dashboard — single-call aggregation of recent traces, due review cards,
      current streak, and total trace count for the dashboard widget.

Other trace-related concerns live in:
    - `traces.py` — run, fork (the execution surface)
    - `traces_save.py` — save, list
    - `traces_share.py` — share links, shared-trace fetch and fork
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, Header, Request
from httpx import AsyncClient
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_http_client, get_profile_id_for_user
from app.rate_limit_decorator import _rate_limit
from app.routers.auth import get_current_user
from app.routers.review import _calculate_streak
from app.services.errors import auth_required_401

logger = logging.getLogger("cognitrace.dashboard")

router = APIRouter()


class DashboardResponse(BaseModel):
    traces: list
    due_cards: list
    streak: int
    total_traces: int


@router.get("/dashboard", response_model=DashboardResponse)
@_rate_limit("60/minute")
async def get_dashboard(
    request: Request,
    authorization: str | None = Header(None),
    client: AsyncClient = Depends(get_http_client),
):
    """Return recent traces, due review cards, current streak, and total count.

    Aggregates four Supabase reads into one round trip so the dashboard widget
    can render in a single fetch. The streak value is always computed by
    `review._calculate_streak` rather than a hardcoded fallback so the
    analytics on the page footer remain aligned with the real activity log.
    """
    if not authorization:
        raise auth_required_401()

    user = await get_current_user(request, authorization)
    profile_id = await get_profile_id_for_user(user.get("id", ""), client)

    streak = await _calculate_streak(
        profile_id or "", settings.supabase_url, settings.supabase_service_key, client
    )

    if not profile_id:
        return DashboardResponse(
            traces=[], due_cards=[], streak=streak, total_traces=int(len([]))
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

    count_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"user_id": f"eq.{profile_id}", "select": "id"},
        headers={**headers, "Prefer": "count=exact"},
    )
    total_traces = len(traces)
    if count_resp.status_code == 200:
        content_range = count_resp.headers.get("content-range", "")
        if "/" in content_range:
            try:
                total_traces = int(content_range.split("/")[-1])
            except ValueError:
                pass

    today = date.today().isoformat()
    cards_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/review_cards",
        params={"user_id": f"eq.{profile_id}", "next_review_date": f"lte.{today}", "select": "*"},
        headers=headers,
    )
    due_cards = cards_resp.json() if cards_resp.status_code == 200 else []

    return DashboardResponse(
        traces=traces,
        due_cards=[{**c, "due": True} for c in due_cards],
        streak=streak,
        total_traces=total_traces,
    )
