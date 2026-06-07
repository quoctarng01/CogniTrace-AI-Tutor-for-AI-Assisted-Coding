"""
Review router — spaced repetition review endpoints.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.config import settings
from app.routers.auth import get_current_user
from app.dependencies import get_profile_id_for_user

logger = logging.getLogger("codescope.review")

router = APIRouter()


async def _calculate_streak(user_id: str, supabase_url: str, supabase_key: str) -> int:
    """
    Count consecutive days with at least 1 completed review, working backwards from today.
    Returns 0 if no reviews today.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
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
    
    Returns: (new_ef, new_interval, new_repetitions, next_review_date)
    """
    # Update easiness factor
    # EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
    new_ef = easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(MIN_EF, new_ef)  # Minimum EF is 1.3
    
    # Calculate new interval
    if quality < 3:
        # Failed — reset to 1 day
        new_interval = 1
        new_repetitions = 0
    else:
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval_days * new_ef)
        new_repetitions = repetitions + 1
    
    next_review = date.today()
    if quality >= 3:
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
    trace: Optional[dict] = None

class DueReviewsResponse(BaseModel):
    cards: list[ReviewCardResponse]
    streak: int
    total_due: int


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/due", response_model=DueReviewsResponse)
async def get_due_reviews(
    authorization: str = Header(None),
):
    """
    Get all review cards that are due for review today.

    Auth: Required (Pro users only)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(authorization)
    user_id = user.get("id", "")

    # Map user UUID (auth.users.id) to profile_id (profiles.id)
    profile_id = await get_profile_id_for_user(user_id)

    if not profile_id:
        return DueReviewsResponse(cards=[], streak=0, total_due=0)

    today = date.today().isoformat()

    async with httpx.AsyncClient(timeout=10.0) as client:
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


@router.get("/{card_id}")
async def get_review_card(
    card_id: str,
    authorization: str = Header(None),
):
    """
    Get a single review card with its full trace and steps.
    Called by the /review/[card_id] page — one call, full data.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(authorization)
    user_id = user.get("id", "")

    # Map user UUID (auth.users.id) to profile_id (profiles.id)
    profile_id = await get_profile_id_for_user(user_id)

    if not profile_id:
        raise HTTPException(status_code=404, detail="User profile not found")

    async with httpx.AsyncClient(timeout=10.0) as client:
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

    steps = json.loads(trace_data.get("steps", "[]")) if trace_data.get("steps") else []

    return ReviewCardResponse(
        id=card["id"],
        trace_id=card["trace_id"],
        concept_tag=card.get("concept_tag", ""),
        next_review_date=card.get("next_review_date", ""),
        interval_days=card.get("interval_days", 1),
        easiness_factor=card.get("easiness_factor", 2.5),
        repetitions=card.get("repetitions", 0),
        due=True,
        trace={
            **trace_data,
            "steps": steps,
        },
    )


@router.post("/{card_id}")
async def submit_review(
    card_id: str,
    req: ReviewRatingRequest,
    authorization: str = Header(None),
):
    """
    Submit a review rating for a card.

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

    user = await get_current_user(authorization)
    user_id = user.get("id", "")

    # Map user UUID (auth.users.id) to profile_id (profiles.id)
    profile_id = await get_profile_id_for_user(user_id)

    if not profile_id:
        raise HTTPException(status_code=404, detail="User profile not found")

    async with httpx.AsyncClient(timeout=10.0) as client:
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

    async with httpx.AsyncClient(timeout=10.0) as client:
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
                "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
            },
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


class GradeRequest(BaseModel):
    card_id: str
    user_answer: str


@router.post("/grade")
async def grade_review_card(
    req: GradeRequest,
    authorization: str = Header(None),
):
    """Grade a user's typed explanation for active recall review."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    user = await get_current_user(authorization)
    user_id = user.get("id", "")
    profile_id = await get_profile_id_for_user(user_id)
    if not profile_id:
        raise HTTPException(status_code=404, detail="User profile not found")

    # Fetch card and trace details from Supabase
    async with httpx.AsyncClient(timeout=10.0) as client:
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

    # Grade user answer via LLM
    from app.services.llm_router import llm_router
    result = await llm_router.grade_explanation(code, steps_json, req.user_answer)
    return result
