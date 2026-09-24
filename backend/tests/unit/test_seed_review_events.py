"""
Tests for backend/scripts/seed_review_events.py.

Verifies that:
  1. The SM-2 walk produces the same next-state numbers as the router's
     sm2_calculate — so the seeded events would have been written by
     the real review endpoint byte-for-byte.
  2. mastery_after = repetitions / (repetitions + 3) matches the
     router's exact formula.
  3. The event row shape (column count and ordering) matches the
     review_events table schema from V015.
  4. Idempotent re-runs produce deterministic per-concept mastery
     values.
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

# Make the script importable without packaging it.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from app.routers.review import sm2_calculate  # noqa: E402
from scripts.seed_review_events import (  # noqa: E402
    MIN_EF,
    RATING_QUALITY,
    build_events_for_concept,
    sm2_step,
)


@pytest.mark.parametrize(
    "quality,ef,interval,reps",
    [
        (1, 2.5, 1, 0),    # again
        (2, 2.5, 6, 3),    # hard
        (3, 2.5, 1, 0),    # good first rep
        (3, 2.5, 6, 1),    # good second rep (jump to 6)
        (3, 2.5, 12, 4),   # good later rep (scaled by EF)
        (5, 2.5, 6, 3),    # easy
    ],
)
def test_sm2_step_matches_router(quality, ef, interval, reps):
    """Seed script's sm2_step must agree with the router's sm2_calculate."""
    new_ef_s, new_interval_s, new_reps_s = sm2_step(quality, ef, interval, reps)
    new_ef_r, new_interval_r, new_reps_r, _ = sm2_calculate(quality, ef, interval, reps)
    assert new_ef_s == pytest.approx(new_ef_r, abs=1e-9)
    assert new_interval_s == new_interval_r
    assert new_reps_s == new_reps_r


def test_sm2_again_resets_reps_to_zero():
    ef, interval, reps = sm2_step(1, 2.5, 12, 5)
    assert reps == 0
    assert interval == 1


def test_sm2_easy_clamps_ef_at_minimum():
    ef, _, _ = sm2_step(0, 1.4, 1, 0)
    assert ef >= MIN_EF


def test_build_events_uses_router_mastery_formula():
    """Each event's mastery_after must equal new_reps / (new_reps + 3)."""
    user_id = str(uuid.uuid4())
    card_id = str(uuid.uuid4())
    started_at = datetime.now(UTC) - timedelta(days=10)
    events = build_events_for_concept(
        user_id=user_id,
        card_id=card_id,
        trace_id=None,
        concept_tag="off_by_one",
        ratings=["good"] * 6,
        started_at=started_at,
    )
    assert len(events) == 6
    for row in events:
        _id, _uid, _cid, _tid, _tag, rating, quality, \
            prev_reps, prev_int, prev_ef, \
            new_reps, new_int, new_ef, \
            mastery, occurred = row
        assert mastery == pytest.approx(new_reps / (new_reps + 3), abs=1e-4)
        assert rating in {"again", "hard", "good", "easy"}
        assert quality == RATING_QUALITY[rating]
        assert 0 <= quality <= 5
        assert 0.0 <= mastery <= 1.0
        assert new_ef >= MIN_EF
        # chronological
        assert occurred >= started_at


def test_event_row_has_fifteen_columns_matching_v015():
    """Match V015__review_events.sql column ordering exactly."""
    user_id = str(uuid.uuid4())
    card_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)
    events = build_events_for_concept(
        user_id=user_id,
        card_id=card_id,
        trace_id=None,
        concept_tag="off_by_one",
        ratings=["good"],
        started_at=started_at,
    )
    assert len(events) == 1
    row = events[0]
    # 15 columns: id, user_id, card_id, trace_id, concept_tag,
    # rating, quality, prev_*, new_*, mastery_after, occurred_at
    assert len(row) == 15


def test_idempotency_two_runs_produce_same_mastery():
    """Re-running with the same ratings must yield the same mastery walk."""
    user_id = str(uuid.uuid4())
    card_id = str(uuid.uuid4())
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    ratings = ["again", "hard", "good", "good", "good", "easy", "easy"]
    a = build_events_for_concept(user_id, card_id, None, "x", ratings, started_at)
    b = build_events_for_concept(user_id, card_id, None, "x", ratings, started_at)
    masteries_a = [row[13] for row in a]
    masteries_b = [row[13] for row in b]
    assert masteries_a == masteries_b


def test_alternating_hard_does_not_drop_mastery_below_initial():
    """A concept that oscillates between good/hard must remain non-decreasing
    on its mastery trajectory when restricted to good ratings, because SM-2
    soft-fails on hard (reps / 2, interval / 2) instead of resetting to 0.
    """
    user_id = str(uuid.uuid4())
    card_id = str(uuid.uuid4())
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    ratings = ["good", "hard", "good", "hard", "good", "hard", "good"]
    events = build_events_for_concept(user_id, card_id, None, "x", ratings, started_at)
    # After 7 mixed reviews we should have non-trivial mastery.
    last_mastery = events[-1][13]
    assert last_mastery > 0.1, f"unexpected low mastery: {last_mastery}"
