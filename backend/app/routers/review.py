"""
Review router — spaced repetition review endpoints.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_http_client, get_profile_id_for_user
from app.routers.auth import get_current_user

logger = logging.getLogger("codescope.review")

router = APIRouter()


# Curated palette for the mastery-trajectory visualization.
# Index = slot; assigned in stable order so each concept_tag gets a
# deterministic colour across renders and across users (as long as the
# user has < len(PALETTE) concepts).
_TRAJECTORY_PALETTE: list[str] = [
    "#7c3aed",  # violet
    "#0891b2",  # cyan
    "#db2777",  # pink
    "#16a34a",  # green
    "#ea580c",  # orange
    "#2563eb",  # blue
    "#ca8a04",  # amber
    "#dc2626",  # red
]


def _color_for_concept(slot: int) -> str:
    return _TRAJECTORY_PALETTE[slot % len(_TRAJECTORY_PALETTE)]


def _compute_trajectory(
    events: list[dict],
    days: int,
) -> dict:
    """Aggregate a flat list of review_events into the trajectory shape
    the frontend expects.

    Input events come ordered newest-first from Supabase; we sort
    ascending inside this function so the resulting points are
    chronological.
    """
    from collections import defaultdict

    if not events:
        return {
            "concepts": [],
            "date_range": {"start": None, "end": None},
            "total_events": 0,
        }

    sorted_events = sorted(events, key=lambda e: e["occurred_at"])

    # Group by concept_tag, preserving first-seen order so the colour
    # palette is deterministic across renders.
    by_concept: dict[str, list[dict]] = defaultdict(list)
    first_seen: dict[str, int] = {}
    for ev in sorted_events:
        tag = ev["concept_tag"]
        if tag not in first_seen:
            first_seen[tag] = len(first_seen)
        by_concept[tag].append(ev)

    concepts: list[dict] = []
    # Recency window for the "recent_miss" pulse: events in the last
    # 3 calendar days relative to *today* (the most recent event in
    # the window is always ≤ today). Window-relative would be wrong
    # because a 30-day window's "last 3 days" depends on the user's
    # earliest activity, not on recency.
    today = datetime.now(timezone.utc).date()
    pulse_cutoff = (today - timedelta(days=3)).isoformat()

    for tag, ev_list in by_concept.items():
        slot = first_seen[tag]
        points = [
            {
                "date": ev["occurred_at"][:10],  # YYYY-MM-DD
                "mastery": float(ev["mastery_after"]),
                "rating": ev["rating"],
                "repetitions": int(ev["new_repetitions"]),
                "interval_days": int(ev["new_interval_days"]),
            }
            for ev in ev_list
        ]
        # Window-aware recent-miss: any hard/again in the last 3 days
        # of the trajectory window. This is what the SVG pulses on.
        recent_miss = any(
            p["date"] >= pulse_cutoff and p["rating"] in ("again", "hard")
            for p in points
        )
        concepts.append(
            {
                "concept_tag": tag,
                "color": _color_for_concept(slot),
                "total_reviews": len(points),
                "current_mastery": points[-1]["mastery"],
                "recent_miss": recent_miss,
                "points": points,
            }
        )

    return {
        "concepts": concepts,
        "date_range": {
            "start": sorted_events[0]["occurred_at"][:10],
            "end": sorted_events[-1]["occurred_at"][:10],
        },
        "total_events": len(sorted_events),
    }


async def _calculate_streak(user_id: str, supabase_url: str, supabase_key: str, client: httpx.AsyncClient | None = None) -> int:
    """
    Count consecutive days with at least 1 completed review, working backwards from today.
    Returns 0 if no reviews today.
    """
    if client is not None:
        resp = await client.get(
            f"{supabase_url}/rest/v1/review_cards",
            params={
                "user_id": f"eq.{user_id}",
                "select": "last_reviewed_at",
                "order": "last_reviewed_at.desc",
                "limit": "100",
            },
            headers={
                "Authorization": f"Bearer {supabase_key}",
                "apikey": supabase_key,
            },
        )
    else:
        async with httpx.AsyncClient(timeout=10.0) as temp_client:
            resp = await temp_client.get(
                f"{supabase_url}/rest/v1/review_cards",
                params={
                    "user_id": f"eq.{user_id}",
                    "select": "last_reviewed_at",
                    "order": "last_reviewed_at.desc",
                    "limit": "100",
                },
                headers={
                    "Authorization": f"Bearer {supabase_key}",
                    "apikey": supabase_key,
                },
            )

    if resp.status_code != 200:
        return 0

    cards = resp.json()

    # Group reviewed dates
    reviewed_dates: set[str] = set()
    for card in cards:
        ts = card.get("last_reviewed_at")
        if ts:
            reviewed_dates.add(ts[:10])  # YYYY-MM-DD

    # Count consecutive days from today backwards (or yesterday if today is not yet reviewed)
    streak = 0
    check_date = date.today()

    if check_date.isoformat() not in reviewed_dates:
        yesterday = check_date - timedelta(days=1)
        if yesterday.isoformat() in reviewed_dates:
            check_date = yesterday
        else:
            return 0

    while True:
        date_str = check_date.isoformat()
        if date_str in reviewed_dates:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return streak

# ── SM-2 Algorithm ────────────────────────────────────────────────

"""
SuperMemo 2 (SM-2) Algorithm Implementation.

Quality ratings:
  0 — Complete blackout, no recall
  1 — Incorrect, but remembered upon seeing answer
  2 — Incorrect, but answer seemed easy to recall
  3 — Correct with serious difficulty
  4 — Correct with some hesitation
  5 — Perfect recall

For simplicity, we map: again=1, hard=2, good=3, easy=5
"""

MIN_EF = 1.3  # Minimum easiness factor

def sm2_calculate(
    quality: int,  # 0-5
    easiness_factor: float,
    interval_days: int,
    repetitions: int,
) -> tuple[float, int, int, date]:
    """
    Calculate the next review parameters using SM-2.
    Supports a soft-fail logic for quality=2 (Hard rating) to avoid resetting repetitions to 0.
    
    Returns: (new_ef, new_interval, new_repetitions, next_review_date)
    """
    # Update easiness factor
    # EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
    new_ef = easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(MIN_EF, new_ef)  # Minimum EF is 1.3

    # Calculate new interval
    if quality < 2:
        # Failed completely ("again") — reset to 1 day
        new_interval = 1
        new_repetitions = 0
    elif quality == 2:
        # Soft-fail ("hard") — halve repetitions and interval
        new_repetitions = max(1, repetitions // 2)
        new_interval = max(1, round(interval_days * 0.5))
    else:
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval_days * new_ef)
        new_repetitions = repetitions + 1

    next_review = date.today()
    # For quality >= 2, we schedule it in the future
    if quality >= 2:
        from datetime import timedelta
        next_review = date.today() + timedelta(days=new_interval)

    return new_ef, new_interval, new_repetitions, next_review

# ── Request/Response Models ───────────────────────────────────────

class ReviewRatingRequest(BaseModel):
    rating: str  # "again" | "hard" | "good" | "easy"

RATING_MAP = {"again": 1, "hard": 2, "good": 3, "easy": 5}

class ReviewCardResponse(BaseModel):
    model_config = {"extra": "ignore"}

    id: str
    trace_id: str
    concept_tag: str
    next_review_date: str
    interval_days: int
    easiness_factor: float
    repetitions: int
    due: bool = False
    trace: dict | None = None
    code_repair_challenge: str | None = None

class DueReviewsResponse(BaseModel):
    cards: list[ReviewCardResponse]
    streak: int
    total_due: int


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/due", response_model=DueReviewsResponse)
async def get_due_reviews(
    request: Request = None,
    authorization: str = Header(None),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """
    Get all review cards that are due for review today.

    Auth: Required (Pro users only)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(request, authorization)
    user_id = user.get("id", "")

    # Map user UUID (auth.users.id) to profile_id (profiles.id)
    profile_id = await get_profile_id_for_user(user_id, client)

    if not profile_id:
        return DueReviewsResponse(cards=[], streak=0, total_due=0)

    today = date.today().isoformat()

    resp = await client.get(
        f"{settings.supabase_url}/rest/v1/review_cards",
        params={
            "user_id": f"eq.{profile_id}",
            "next_review_date": f"lte.{today}",
            "select": "*",
        },
        headers={
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
        },
    )
    cards = resp.json() if resp.status_code == 200 else []

    for card in cards:
        card["due"] = True

    streak = await _calculate_streak(profile_id, settings.supabase_url, settings.supabase_service_key)
    return DueReviewsResponse(cards=cards[:20], streak=streak, total_due=len(cards))


class TrajectoryPoint(BaseModel):
    date: str
    mastery: float
    rating: str
    repetitions: int
    interval_days: int


class TrajectoryConcept(BaseModel):
    concept_tag: str
    color: str
    total_reviews: int
    current_mastery: float
    recent_miss: bool
    points: list[TrajectoryPoint]


class TrajectoryResponse(BaseModel):
    concepts: list[TrajectoryConcept]
    date_range: dict
    total_events: int
    days: int


# NOTE: /trajectory is registered BEFORE /{card_id} on purpose — FastAPI
# matches routes in registration order and the `/{card_id}` catch-all would
# otherwise swallow `/trajectory` (treat it as card_id="trajectory") and
# return "Card not found". Keep this above the catch-all.
@router.get("/trajectory", response_model=TrajectoryResponse)
async def get_mastery_trajectory(
    request: Request,
    days: int = 30,
    authorization: str | None = Header(None),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """Per-concept mastery trajectory for the last N days.

    Backed by the V015 ``review_events`` append-only log. Used by the
    ``/dashboard/mastery`` page (THESIS-05 §2). One Supabase read;
    aggregation happens in Python.

    Auth: required (the trajectory is per-user and exposes review
    history which is sensitive).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    if days < 1 or days > 365:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_DAYS", "message": "days must be in [1, 365]"},
        )

    user = await get_current_user(request, authorization)
    profile_id = await get_profile_id_for_user(user.get("id", ""), client)

    if not profile_id:
        return TrajectoryResponse(
            concepts=[],
            date_range={"start": None, "end": None},
            total_events=0,
            days=days,
        )

    # Supabase expects ISO-8601. We compute the cutoff in UTC.
    cutoff = datetime.now(UTC) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    resp = await client.get(
        f"{settings.supabase_url}/rest/v1/review_events",
        params={
            "user_id": f"eq.{profile_id}",
            "occurred_at": f"gte.{cutoff_iso}",
            "select": "concept_tag,rating,new_repetitions,new_interval_days,mastery_after,occurred_at",
            "order": "occurred_at.desc",
            "limit": "5000",
        },
        headers={
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
        },
    )
    if resp.status_code != 200:
        # Treat Supabase failure as an empty trajectory — the page will
        # render the empty state rather than 500-ing.
        logger.warning("trajectory_fetch_failed", extra={"status": resp.status_code})
        return TrajectoryResponse(
            concepts=[],
            date_range={"start": None, "end": None},
            total_events=0,
            days=days,
        )

    events = resp.json()
    agg = _compute_trajectory(events, days)
    return TrajectoryResponse(
        concepts=agg["concepts"],
        date_range=agg["date_range"],
        total_events=agg["total_events"],
        days=days,
    )


@router.get("/{card_id}")
async def get_review_card(
    card_id: str,
    request: Request = None,
    authorization: str = Header(None),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """
    Get a single review card with its full trace and steps.
    Called by the /review/[card_id] page — one call, full data.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(request, authorization)
    user_id = user.get("id", "")

    # Map user UUID (auth.users.id) to profile_id (profiles.id)
    profile_id = await get_profile_id_for_user(user_id, client)

    if not profile_id:
        raise HTTPException(status_code=404, detail="User profile not found")

    headers = {
        "Authorization": f"Bearer {authorization[7:]}",
        "apikey": settings.supabase_service_key,
    }

    card_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/review_cards",
        params={"id": f"eq.{card_id}", "user_id": f"eq.{profile_id}", "select": "*"},
        headers=headers,
    )
    cards = card_resp.json() if card_resp.status_code == 200 else []
    if not cards:
        raise HTTPException(status_code=404, detail="Card not found")
    card = cards[0]

    trace_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"id": f"eq.{card['trace_id']}", "select": "*"},
        headers=headers,
    )
    trace_data = trace_resp.json()[0] if trace_resp.status_code == 200 and trace_resp.json() else {}

    steps_raw = trace_data.get("steps")
    if isinstance(steps_raw, list):
        steps = steps_raw
    elif isinstance(steps_raw, str):
        try:
            steps = json.loads(steps_raw)
        except json.JSONDecodeError:
            steps = []
    else:
        steps = []

    concept_tag = card.get("concept_tag", "")
    code_repair_challenge = None
    MISCONCEPTION_TAGS = {
        "off_by_one",
        "unexecuted_iteration",
        "none_dereference",
        "state_mutation_confusion",
        "conditional_evaluation_error",
        "type_confusion",
        "general_logic_error"
    }

    if concept_tag in MISCONCEPTION_TAGS:
        from app.services.llm_router import llm_router
        custom_settings = None
        if profile_id:
            from app.dependencies import get_profile_settings
            custom_settings = await get_profile_settings(profile_id, client)
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
            code_repair_challenge = await llm_router.generate_code_repair_challenge(
                original_code=trace_data.get("code", ""),
                misconception_tag=concept_tag,
                **kwargs
            )
        except Exception as e:
            logger.error("failed_to_generate_code_repair_challenge", extra={"error": str(e)})

    return ReviewCardResponse(
        id=card["id"],
        trace_id=card["trace_id"],
        concept_tag=concept_tag,
        next_review_date=card.get("next_review_date", ""),
        interval_days=card.get("interval_days", 1),
        easiness_factor=card.get("easiness_factor", 2.5),
        repetitions=card.get("repetitions", 0),
        due=True,
        trace={
            **trace_data,
            "steps": steps,
        },
        code_repair_challenge=code_repair_challenge,
    )


class GradeRequest(BaseModel):
    card_id: str
    user_answer: str


@router.post("/grade")
async def grade_review_card(
    req: GradeRequest,
    request: Request = None,
    authorization: str = Header(None),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """Grade a user's typed explanation for active recall review."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(request, authorization)
    user_id = user.get("id", "")
    profile_id = await get_profile_id_for_user(user_id, client)
    if not profile_id:
        raise HTTPException(status_code=404, detail="User profile not found")

    # Fetch card and trace details from Supabase
    headers = {
        "Authorization": f"Bearer {authorization[7:]}",
        "apikey": settings.supabase_service_key,
    }
    card_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/review_cards",
        params={"id": f"eq.{req.card_id}", "user_id": f"eq.{profile_id}", "select": "*"},
        headers=headers,
    )
    cards = card_resp.json() if card_resp.status_code == 200 else []
    if not cards:
        raise HTTPException(status_code=404, detail="Card not found")
    card = cards[0]

    trace_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"id": f"eq.{card['trace_id']}", "select": "*"},
        headers=headers,
    )
    trace_data = trace_resp.json()[0] if trace_resp.status_code == 200 and trace_resp.json() else {}

    code = trace_data.get("code", "")
    steps = trace_data.get("steps", "[]")

    if not isinstance(steps, str):
        steps_json = json.dumps(steps)
    else:
        steps_json = steps

    concept_tag = card.get("concept_tag", "")
    MISCONCEPTION_TAGS = {
        "off_by_one",
        "unexecuted_iteration",
        "none_dereference",
        "state_mutation_confusion",
        "conditional_evaluation_error",
        "type_confusion",
        "general_logic_error"
    }

    from app.services.llm_router import llm_router
    custom_settings = None
    if profile_id:
        from app.dependencies import get_profile_settings
        custom_settings = await get_profile_settings(profile_id, client)
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
    if concept_tag in MISCONCEPTION_TAGS:
        result = await llm_router.grade_code_repair(code, concept_tag, req.user_answer, **kwargs)
    else:
        result = await llm_router.grade_explanation(code, steps_json, req.user_answer, **kwargs)
    return result


@router.post("/{card_id}")
async def submit_review(
    card_id: str,
    req: ReviewRatingRequest,
    request: Request = None,
    authorization: str = Header(None),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """
    Submit a review rating (again/hard/good/easy) for a card.
    Updates the card's SM-2 parameters and schedules the next review.

    Auth: Required (Pro users only)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    if req.rating not in RATING_MAP:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_RATING", "message": "Rating must be: again, hard, good, or easy"},
        )

    quality = RATING_MAP[req.rating]

    user = await get_current_user(request, authorization)
    user_id = user.get("id", "")

    # Map user UUID (auth.users.id) to profile_id (profiles.id)
    profile_id = await get_profile_id_for_user(user_id, client)

    if not profile_id:
        raise HTTPException(status_code=404, detail="User profile not found")

    resp = await client.get(
        f"{settings.supabase_url}/rest/v1/review_cards",
        params={"id": f"eq.{card_id}", "user_id": f"eq.{profile_id}", "select": "*"},
        headers={
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
        },
    )
    cards = resp.json() if resp.status_code == 200 else []
    if not cards:
        raise HTTPException(status_code=404, detail="Card not found")
    card = cards[0]

    new_ef, new_interval, new_reps, next_date = sm2_calculate(
        quality, card["easiness_factor"], card["interval_days"], card["repetitions"]
    )

    await client.patch(
        f"{settings.supabase_url}/rest/v1/review_cards",
        params={"id": f"eq.{card_id}"},
        headers={
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={
            "easiness_factor": round(new_ef, 2),
            "interval_days": new_interval,
            "repetitions": new_reps,
            "next_review_date": next_date.isoformat(),
            "last_reviewed_at": datetime.now(UTC).isoformat(),
        },
    )

    # Append-only event log for the mastery-trajectory visualization
    # (docs/THESIS-05-FUTURE-WORK-TIER1.md §2). We use the same HTTP
    # client so the insert is rolled into the same auth context.
    # Best-effort: a failure here must not break the review itself.
    try:
        mastery_after = new_reps / (new_reps + 3)  # 0..1 monotone proxy
        await client.post(
            f"{settings.supabase_url}/rest/v1/review_events",
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={
                "user_id": profile_id,
                "card_id": card_id,
                "trace_id": card.get("trace_id"),
                "concept_tag": card["concept_tag"],
                "rating": req.rating,
                "quality": quality,
                "prev_repetitions": int(card["repetitions"]),
                "prev_interval_days": int(card["interval_days"]),
                "prev_easiness_factor": float(card["easiness_factor"]),
                "new_repetitions": int(new_reps),
                "new_interval_days": int(new_interval),
                "new_easiness_factor": round(float(new_ef), 2),
                "mastery_after": round(float(mastery_after), 4),
            },
        )
    except Exception as exc:  # pragma: no cover — defensive only
        logger.warning(
            "review_event_log_failed",
            extra={"card_id": card_id, "error": str(exc)},
        )

    logger.info(
        "review_submitted",
        extra={"card_id": card_id, "rating": req.rating, "quality": quality, "next_interval": new_interval},
    )

    return {
        "card_id": card_id,
        "new_interval_days": new_interval,
        "new_ef": round(new_ef, 2),
        "new_repetitions": new_reps,
        "next_review_date": next_date.isoformat(),
    }





