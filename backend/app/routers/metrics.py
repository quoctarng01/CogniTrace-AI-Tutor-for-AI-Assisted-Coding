"""GET /api/metrics/cache-hit-rate — cache-hit rollup for the dashboard.

Workstream 10 — exposes the `llm_call_metrics_daily` rollup to the
frontend dashboard. The endpoint reads directly from Postgres via the
service-role Supabase key (the same pattern used by every other
authenticated Supabase call in the codebase).

Why an HTTP endpoint instead of a Postgres view:
- We want to keep the SQL surface narrow (no Postgres view defined
  outside migrations), and one file is easier to evolve than migrations.
- We want the same auth + rate-limit treatment as every other API route.

The matching rollup job lives in `app.services.metrics_aggregator`.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from httpx import AsyncClient
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_http_client
from app.rate_limit_decorator import _rate_limit
from app.routers.auth import get_current_user

logger = logging.getLogger("cognitrace.metrics")

router = APIRouter()


class CacheHitRateRow(BaseModel):
    day: str
    provider: str
    cache_hit_rate: float
    p50_latency_ms: int
    p95_latency_ms: int
    total_calls: int


class CacheHitRateResponse(BaseModel):
    window_days: int
    rows: list[CacheHitRateRow]


_WINDOW_PATTERN = re.compile(r"^(\d+)d$")


def _parse_window(window: str) -> int:
    """Parse the `?window=` query value into a day count. Default is 7."""
    m = _WINDOW_PATTERN.match(window or "7d")
    if not m:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_WINDOW", "message": "window must look like `7d` (max 90d)"},
        )
    days = int(m.group(1))
    if days <= 0 or days > 90:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_WINDOW", "message": "window must be 1d-90d"},
        )
    return days


@router.get("/metrics/cache-hit-rate", response_model=CacheHitRateResponse)
@_rate_limit("30/minute")
async def cache_hit_rate(
    request: Request,
    window: str = "7d",
    authorization: str | None = Header(None),
    client: AsyncClient = Depends(get_http_client),
):
    """Return per-day cache hit-rate rollups for the last `window` days.

    Args:
        window: An integer followed by `d`, e.g. `1d`, `7d`, `30d`. Max 90.
        authorization: Bearer token for an authenticated user.

    Returns:
        ``CacheHitRateResponse`` with one row per (day, provider).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    days = _parse_window(window)
    user = await get_current_user(request, authorization)
    if not user.get("id"):
        raise HTTPException(status_code=401, detail="Invalid token")

    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()

    headers = {
        "Authorization": f"Bearer {authorization[7:] if authorization.startswith('Bearer ') else authorization}",
        "apikey": settings.supabase_service_key,
    }

    resp = await client.get(
        f"{settings.supabase_url}/rest/v1/llm_call_metrics_daily",
        params={
            "day": f"gte.{since}",
            "select": "day,provider,cache_hit_rate,p50_latency_ms,p95_latency_ms,total_calls",
            "order": "day.desc,provider.asc",
        },
        headers=headers,
    )

    if resp.status_code != 200:
        logger.warning(
            "metrics_query_failed",
            extra={"status": resp.status_code, "body": resp.text[:200]},
        )
        raise HTTPException(status_code=502, detail="Failed to query metrics")

    raw_rows: list[dict[str, Any]] = resp.json() or []
    rows = [CacheHitRateRow(**row) for row in raw_rows]

    return CacheHitRateResponse(window_days=days, rows=rows)
