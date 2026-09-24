"""Unit tests for `app.services.checkpoint_selector` (T1-C).

Pins the rubric:
  * no concept_tag → DIRECT
  * 0 recent sessions → DIRECT
  * 0 misses in window → DIRECT
  * ≥ 1 miss in last 3 sessions → SCAFFOLDED
  * ≥ 2 misses in last 3 sessions → CONTRASTIVE
  * override_mode bypasses the rubric
  * events for other concepts are filtered out
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.checkpoint_selector import (
    CheckpointMode,
    CheckpointSelection,
    select_checkpoint_mode,
)


def _ev(rating: str, days_ago: int, concept: str = "loop") -> dict:
    """Build a review_event dict `days_ago` back from now."""
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {"rating": rating, "occurred_at": ts, "concept_tag": concept}


# ── Empty / trivial cases ────────────────────────────────────────


def test_no_concept_tag_returns_direct():
    sel = select_checkpoint_mode(concept_tag=None)
    assert sel.mode == CheckpointMode.DIRECT
    assert "no_concept_tag" in sel.rationale


def test_no_recent_events_returns_direct():
    sel = select_checkpoint_mode(concept_tag="loop")
    assert sel.mode == CheckpointMode.DIRECT
    assert "no_recent_sessions" in sel.rationale


def test_only_good_ratings_returns_direct():
    events = [_ev("good", 1), _ev("hard", 2), _ev("good", 3)]
    sel = select_checkpoint_mode(concept_tag="loop", recent_review_events=events)
    assert sel.mode == CheckpointMode.DIRECT
    assert sel.recent_miss_count == 0


# ── Miss thresholds ──────────────────────────────────────────────


def test_one_miss_returns_scaffolded():
    events = [_ev("good", 0), _ev("again", 1)]  # 1 miss
    sel = select_checkpoint_mode(concept_tag="loop", recent_review_events=events)
    assert sel.mode == CheckpointMode.SCAFFOLDED
    assert sel.recent_miss_count >= 1


def test_two_misses_return_contrastive():
    events = [_ev("again", 0), _ev("again", 1), _ev("good", 2)]
    sel = select_checkpoint_mode(concept_tag="loop", recent_review_events=events)
    assert sel.mode == CheckpointMode.CONTRASTIVE
    assert sel.recent_miss_count >= 2


# ── Concept filtering ────────────────────────────────────────────


def test_other_concept_misses_do_not_trigger_adaptation():
    """A miss on a different concept must not push `loop` into scaffolded."""
    events = [
        _ev("again", 0, concept="recursion"),
        _ev("again", 1, concept="recursion"),
        _ev("good", 2, concept="loop"),
    ]
    sel = select_checkpoint_mode(concept_tag="loop", recent_review_events=events)
    assert sel.mode == CheckpointMode.DIRECT


# ── Window ───────────────────────────────────────────────────────


def test_old_misses_outside_top_three_sessions_are_ignored():
    """Only the 3 most-recent distinct session days count toward the rubric.

    With 2 old misses (day -10, -11) and a recent good (day 0), the
    recent-3-day window includes [today, -10, -11] so old misses DO
    count toward miss_count. To produce a pure "old misses ignored" case
    we need the recent session to push the older days out of the window.
    """
    events = [
        _ev("good", 0),   # session day 0
        _ev("good", 1),   # session day 1
        _ev("good", 2),   # session day 2 — fills the 3-day window
        _ev("again", 10), # outside the window
        _ev("again", 11),
    ]
    sel = select_checkpoint_mode(concept_tag="loop", recent_review_events=events)
    assert sel.mode == CheckpointMode.DIRECT
    assert sel.recent_miss_count == 0


# ── Override ─────────────────────────────────────────────────────


def test_override_mode_bypasses_rubric():
    sel = select_checkpoint_mode(
        concept_tag="loop",
        recent_review_events=[],
        override_mode=CheckpointMode.CONTRASTIVE,
    )
    assert sel.mode == CheckpointMode.CONTRASTIVE
    assert "explicit_override" in sel.rationale


def test_override_mode_accepts_string():
    sel = select_checkpoint_mode(
        concept_tag="loop",
        override_mode="scaffolded",
    )
    assert sel.mode == CheckpointMode.SCAFFOLDED


# ── Output shape ─────────────────────────────────────────────────


def test_selection_is_frozen_dataclass():
    sel = select_checkpoint_mode(concept_tag=None)
    assert isinstance(sel, CheckpointSelection)
    assert sel.mode in CheckpointMode
    assert isinstance(sel.rationale, str)
    assert isinstance(sel.recent_miss_count, int)
    assert isinstance(sel.recent_session_count, int)
