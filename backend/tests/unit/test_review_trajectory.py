"""Unit tests for the mastery-trajectory aggregator (THESIS-05 §2).

These tests exercise the pure-Python _compute_trajectory helper in
isolation — no Supabase, no network. The endpoint that calls it
(GET /api/review/trajectory) is covered by the integration suite.
"""
from datetime import datetime, timezone, timedelta

import pytest

from app.routers.review import _compute_trajectory


def _ev(
    concept: str,
    rating: str,
    quality: int,
    mastery: float,
    reps: int,
    days_ago: int,
    interval: int = 1,
) -> dict:
    """Build a review_events-shaped dict for testing."""
    occurred = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "concept_tag": concept,
        "rating": rating,
        "quality": quality,
        "mastery_after": mastery,
        "new_repetitions": reps,
        "new_interval_days": interval,
        "occurred_at": occurred.isoformat(),
    }


class TestComputeTrajectory:
    def test_empty_input_returns_empty_payload(self):
        out = _compute_trajectory([], days=30)
        assert out["concepts"] == []
        assert out["date_range"] == {"start": None, "end": None}
        assert out["total_events"] == 0

    def test_single_concept_returns_one_line(self):
        events = [
            _ev("loop_off_by_one", "again", 1, 0.0, 0, days_ago=5),
            _ev("loop_off_by_one", "good", 3, 0.5, 1, days_ago=3),
            _ev("loop_off_by_one", "easy", 5, 0.8, 3, days_ago=1),
        ]
        out = _compute_trajectory(events, days=30)
        assert out["total_events"] == 3
        assert len(out["concepts"]) == 1

        concept = out["concepts"][0]
        assert concept["concept_tag"] == "loop_off_by_one"
        assert concept["total_reviews"] == 3
        assert concept["current_mastery"] == 0.8
        assert concept["recent_miss"] is False  # last 3 all good/easy
        # Points are sorted ascending by date — oldest first.
        assert concept["points"][0]["mastery"] == 0.0
        assert concept["points"][-1]["mastery"] == 0.8

    def test_multiple_concepts_get_distinct_colours(self):
        events = [
            _ev("alpha", "good", 3, 0.5, 1, days_ago=4),
            _ev("beta", "good", 3, 0.5, 1, days_ago=4),
            _ev("gamma", "good", 3, 0.5, 1, days_ago=4),
        ]
        out = _compute_trajectory(events, days=30)
        colors = {c["concept_tag"]: c["color"] for c in out["concepts"]}
        assert len(set(colors.values())) == 3, (
            f"Expected 3 distinct colors, got {colors}"
        )

    def test_color_assignment_is_deterministic(self):
        """First-seen slot wins regardless of input order."""
        events = [
            _ev("zzz", "good", 3, 0.5, 1, days_ago=3),
            _ev("aaa", "good", 3, 0.5, 1, days_ago=2),
        ]
        out = _compute_trajectory(events, days=30)
        colors = {c["concept_tag"]: c["color"] for c in out["concepts"]}
        # zzz was first in the sorted list, gets slot 0
        assert colors["zzz"] != colors["aaa"]

    def test_recent_miss_flag_triggers_on_hard_in_last_three(self):
        events = [
            _ev("alpha", "good", 3, 0.5, 1, days_ago=4),
            _ev("alpha", "good", 3, 0.7, 2, days_ago=3),
            _ev("alpha", "hard", 2, 0.4, 1, days_ago=2),
        ]
        out = _compute_trajectory(events, days=30)
        assert out["concepts"][0]["recent_miss"] is True

    def test_recent_miss_flag_clears_when_window_passes(self):
        events = [
            _ev("alpha", "hard", 2, 0.4, 1, days_ago=10),
            _ev("alpha", "good", 3, 0.6, 2, days_ago=2),
        ]
        out = _compute_trajectory(events, days=30)
        # Last 3 points = [the single recent one], no miss
        assert out["concepts"][0]["recent_miss"] is False

    def test_date_range_spans_oldest_to_newest(self):
        events = [
            _ev("alpha", "good", 3, 0.5, 1, days_ago=10),
            _ev("alpha", "good", 3, 0.6, 2, days_ago=5),
            _ev("alpha", "good", 3, 0.7, 3, days_ago=1),
        ]
        out = _compute_trajectory(events, days=30)
        assert out["date_range"]["start"] <= out["date_range"]["end"]
        # Both are YYYY-MM-DD strings of length 10
        assert len(out["date_range"]["start"]) == 10
        assert len(out["date_range"]["end"]) == 10

    def test_points_truncate_date_to_ymd(self):
        events = [_ev("alpha", "good", 3, 0.5, 1, days_ago=2)]
        out = _compute_trajectory(events, days=30)
        point = out["concepts"][0]["points"][0]
        assert len(point["date"]) == 10  # YYYY-MM-DD
        assert "T" not in point["date"]

    def test_input_order_does_not_affect_output(self):
        """Reversed input should still produce the same trajectory."""
        forward = [
            _ev("alpha", "good", 3, 0.4, 1, days_ago=3),
            _ev("alpha", "good", 3, 0.6, 2, days_ago=2),
            _ev("alpha", "easy", 5, 0.8, 3, days_ago=1),
        ]
        backward = list(reversed(forward))
        a = _compute_trajectory(forward, days=30)
        b = _compute_trajectory(backward, days=30)
        # Same shape, same mastery endpoints, same point count
        assert a["concepts"][0]["points"] == b["concepts"][0]["points"]

    def test_palette_wraps_past_eight_concepts(self):
        # Use 10 concepts to verify modulo behaviour
        events = [
            _ev(f"c{i}", "good", 3, 0.5, 1, days_ago=1) for i in range(10)
        ]
        out = _compute_trajectory(events, days=30)
        colors = [c["color"] for c in out["concepts"]]
        # Slot 0 and slot 8 share a colour (modulo 8)
        assert colors[0] == colors[8]
