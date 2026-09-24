"""Cognitive Load Dashboard — THESIS-05 §1 (T1-A).

Surface: ``GET /api/load/trace/{trace_id}`` — returns a single
``LoadEstimate`` for the given trace.

Inputs are gathered on the server side from existing tables:
  * trace_events ← ``traces.steps`` (the saved tracer events)
  * interaction_events ← ``anonymous_events`` filtered to the trace id
    (pauses, replays, checkpoint submissions)
  * sm2_recent_events ← ``review_events`` for the calling user on the
    trace's primary concept tag, last 30 days

Auth: required for the *user-scoped* signals (interaction + SM-2). The
trace itself may be public; if so we still require auth so we know which
user's SM-2 history to fold in.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings
from app.dependencies import (
    get_http_client,
    get_profile_id_for_user,
    get_supabase_repo,
)
from app.repositories.supabase import SupabaseRepository
from app.services.errors import trace_not_found_404
from app.services.load_estimator import estimate_load

logger = logging.getLogger("cognitrace.load")

router = APIRouter()


async def _fetch_trace_steps(
    repo: SupabaseRepository, trace_id: str
) -> tuple[list[dict], list[str] | None, str | None]:
    """Pull the trace's code + steps + primary concept tag from Postgres.

    Returns ``(steps, concept_tags, user_id)``. Raises a 404 if no
    trace exists. The concept tag is the first non-empty value in
    ``concept_tags`` so the caller can resolve SM-2 events.
    """
    rows = await repo._get(  # noqa: SLF001 — same pattern as fingerprint.py
        "/rest/v1/traces",
        params={
            "id": f"eq.{trace_id}",
            "select": "steps,concept_tags,user_id",
            "limit": "1",
        },
    )
    if not rows:
        raise trace_not_found_404()
    trace = rows[0]
    steps = trace.get("steps") or []
    tags = trace.get("concept_tags") or []
    return steps, tags, trace.get("user_id")


async def _fetch_interaction_events(
    client: httpx.AsyncClient, trace_id: str
) -> list[dict]:
    """Pull anonymous interaction events for the given trace.

    These are emitted by ``lib/analytics.ts::trackEvent`` with a
    ``trace_id`` metadata field. The table is unfiltered because the
    events are anonymous; we filter server-side here.
    """
    if not settings.supabase_url or not settings.supabase_service_key:
        return []
    try:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/anonymous_events",
            params={
                "select": "event_type,metadata,occurred_at",
                # `metadata->>trace_id` is the JSONB lookup PostgREST
                # exposes via the arrow operator. We restrict to events
                # tagged with this trace id; the row limit caps the
                # query so a runaway session can't return megabytes.
                "metadata->>trace_id": f"eq.{trace_id}",
                "order": "occurred_at.asc",
                "limit": "500",
            },
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
            },
        )
        if resp.status_code == 200:
            return resp.json() or []
    except Exception as e:  # pragma: no cover — defensive
        logger.debug("load_interaction_fetch_failed", extra={"error": str(e)})
    return []


async def _fetch_sm2_recent(
    client: httpx.AsyncClient,
    *,
    profile_id: str,
    concept_tag: str | None,
    lookback_days: int = 30,
) -> list[dict]:
    """Pull SM-2 mastery events for the user + concept tag.

    Soft-fails on any error; the load estimator treats an empty list as
    "no signal" rather than crashing.
    """
    if not concept_tag:
        return []
    try:
        cutoff = (datetime.now(UTC) - timedelta(days=lookback_days)).isoformat()
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/review_events",
            params={
                "select": "mastery_after,concept_tag,occurred_at",
                "user_id": f"eq.{profile_id}",
                "concept_tag": f"eq.{concept_tag}",
                "occurred_at": f"gte.{cutoff}",
                "order": "occurred_at.desc",
                "limit": "100",
            },
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
            },
        )
        if resp.status_code == 200:
            return resp.json() or []
    except Exception as e:  # pragma: no cover — defensive
        logger.debug("load_sm2_fetch_failed", extra={"error": str(e)})
    return []


@router.get("/api/load/trace/{trace_id}")
async def get_trace_load(
    trace_id: str,
    repo: Annotated[SupabaseRepository, Depends(get_supabase_repo)],
    client: httpx.AsyncClient = Depends(get_http_client),
    authorization: str | None = Header(None),
):
    """Return the cognitive-load estimate for a saved trace.

    The response includes the 0-100 aggregate score, the three
    sub-component scores (so the dashboard can render a stacked bar),
    and a chronological series of `LoadPoint`s so the panel can draw a
    line chart with hover labels.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization[7:]

    # 1. Pull the trace.
    steps, concept_tags, _trace_user_id = await _fetch_trace_steps(repo, trace_id)

    # 2. Pull the caller's profile id so we can resolve their SM-2.
    user = None
    try:
        from app.routers.auth import get_current_user

        user = await get_current_user(authorization)
    except Exception:
        user = None

    profile_id: str | None = None
    if user and user.get("id"):
        try:
            profile_id = await get_profile_id_for_user(user["id"], client)
        except Exception:
            profile_id = None

    # 3. Pull the inputs in parallel.
    primary_concept = (concept_tags or [None])[0]
    interaction_events_task = asyncio.create_task(
        _fetch_interaction_events(client, trace_id)
    )
    sm2_events_task = asyncio.create_task(
        _fetch_sm2_recent(
            client, profile_id=profile_id or "", concept_tag=primary_concept
        )
    )
    interaction_events, sm2_events = await asyncio.gather(
        interaction_events_task, sm2_events_task
    )

    # 4. Estimate.
    est = estimate_load(
        trace_events=steps,
        interaction_events=interaction_events,
        sm2_recent_events=sm2_events,
    )

    return {
        "trace_id": trace_id,
        "score": est.score,
        "structural": est.structural,
        "interaction": est.interaction,
        "sm2": est.sm2,
        "series": [
            {"t_seconds": p.t_seconds, "score": p.score, "label": p.label}
            for p in est.series
        ],
        "notes": est.notes,
        "primary_concept_tag": primary_concept,
        "events_count": {
            "trace_steps": len(steps),
            "interaction_events": len(interaction_events),
            "sm2_events": len(sm2_events),
        },
    }