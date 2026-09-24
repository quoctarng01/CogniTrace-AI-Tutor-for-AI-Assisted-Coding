"""Unit tests for `app.services.load_estimator` (T1-A).

Pins the 0-100 estimator's contract:

  * score is monotone in load signals (more branches / pauses / lower
    mastery → higher score)
  * the three sub-scores stay in [0, 1]
  * empty inputs return a clean zero (no NaN, no division errors)
  * the `series` list emits one `LoadPoint` per structural event
  * the new typed load-event names (`tracer_pause`,
    `tracer_whatif_replay`, `tutor_checkpoint_miss`) are recognised
    alongside the legacy strings so existing telemetry still contributes
"""
from __future__ import annotations

from app.services.load_estimator import (
    LoadEstimate,
    LoadPoint,
    _interaction_score,
    _sm2_score,
    _structural_score,
    estimate_load,
)


# ── Pure estimator — happy path ────────────────────────────────────


def test_empty_inputs_yield_zero_score():
    est = estimate_load()
    assert isinstance(est, LoadEstimate)
    assert est.score == 0
    assert est.structural == 0.0
    assert est.interaction == 0.0
    assert est.sm2 == 0.0
    assert est.series == []
    assert est.notes == []


def test_structural_load_grows_with_branches_and_loops():
    baseline = _structural_score([])
    sparse = _structural_score(
        [{"opcode": "LINE", "duration_ms": 1, "variables": {}}]
    )
    dense = _structural_score(
        [
            {"opcode": "BEFORE_IF", "duration_ms": 10, "variables": {"x": 1}},
            {"opcode": "BEFORE_FOR", "duration_ms": 10, "variables": {"i": 0}},
            {"opcode": "BEFORE_WHILE", "duration_ms": 10, "variables": {"n": 5}},
            {"opcode": "EXCEPTION", "duration_ms": 5, "variables": {}},
        ]
    )
    assert baseline[0] == 0.0
    assert sparse[0] == 0.0
    assert dense[0] > sparse[0]
    # Series should emit a point for each BEFORE_* entry + the exception
    assert len(dense[1]) == 4


def test_structural_series_emits_branch_and_exception_labels():
    _, points = _structural_score(
        [
            {"opcode": "BEFORE_IF", "duration_ms": 10, "variables": {}},
            {"opcode": "EXCEPTION", "duration_ms": 5, "variables": {}},
        ]
    )
    assert len(points) == 2
    assert isinstance(points[0], LoadPoint)
    assert "if" in points[0].label
    assert "exception" in points[1].label
    # Timestamps accumulate as cumulative_ms grows
    assert points[1].t_seconds > points[0].t_seconds


def test_structural_caps_at_one():
    # Even an absurdly dense trace shouldn't overflow the [0, 1] sub-score.
    events = (
        [{"opcode": "BEFORE_IF", "duration_ms": 1, "variables": {i: i}} for i in range(50)]
        + [{"opcode": "BEFORE_FOR", "duration_ms": 1, "variables": {}} for _ in range(50)]
        + [{"opcode": "EXCEPTION", "duration_ms": 1, "variables": {}} for _ in range(50)]
    )
    score, _ = _structural_score(events)
    assert 0.0 <= score <= 1.0


# ── Interaction sub-score ─────────────────────────────────────────


def test_interaction_recognises_new_typed_event_names():
    events = [
        {"event_type": "tracer_pause", "metadata": {"duration_ms": 12000}},
        {"event_type": "tracer_whatif_replay", "metadata": {}},
        {"event_type": "tutor_checkpoint_miss", "metadata": {}},
    ]
    score, notes = _interaction_score(events)
    # All three contribute — score should be meaningfully above zero
    assert score > 0.0
    assert any("long pauses" in n for n in notes)
    assert any("What-If replays" in n for n in notes)
    assert any("checkpoint misses" in n for n in notes)


def test_interaction_legacy_strings_still_work():
    events = [
        {"event_type": "pause", "metadata": {"duration_ms": 5000}},
        {"event_type": "what_if_replay", "metadata": {}},
        {"event_type": "tutor_checkpoint_submitted", "metadata": {"correct": False}},
    ]
    score, _ = _interaction_score(events)
    assert score > 0.0


def test_interaction_handles_metadata_as_none():
    # The estimator should never crash on a malformed event row.
    events = [
        {"event_type": "tracer_pause"},
        {"event_type": "tracer_whatif_replay"},
    ]
    score, _ = _interaction_score(events)
    assert 0.0 <= score <= 1.0


# ── SM-2 sub-score ───────────────────────────────────────────────


def test_sm2_inverts_mastery():
    # Mastery 1.0 → inverse 0; mastery 0.0 → inverse 1.0
    high_mastery, _ = _sm2_score(1.0, None)
    low_mastery, _ = _sm2_score(0.0, None)
    assert high_mastery < low_mastery
    assert 0.0 <= high_mastery <= 1.0
    assert 0.0 <= low_mastery <= 1.0


def test_sm2_averages_recent_events():
    score, _ = _sm2_score(
        None,
        [{"mastery_after": 0.8}, {"mastery_after": 0.6}, {"mastery_after": 1.0}],
    )
    # avg mastery = 0.8 → inverse = 0.2
    assert abs(score - 0.2) < 1e-9


def test_sm2_no_concept_returns_zero():
    score, _ = _sm2_score(None, None)
    assert score == 0.0


# ── Aggregator ────────────────────────────────────────────────────


def test_estimate_load_combines_three_axes():
    est = estimate_load(
        trace_events=[
            {"opcode": "BEFORE_FOR", "duration_ms": 5, "variables": {"i": 0}},
            {"opcode": "LINE", "duration_ms": 5},
        ],
        interaction_events=[
            {"event_type": "tracer_pause", "metadata": {"duration_ms": 10000}},
        ],
        sm2_recent_events=[{"mastery_after": 0.3}],
    )
    assert 0 <= est.score <= 100
    assert est.structural > 0.0
    assert est.interaction > 0.0
    assert est.sm2 > 0.0
    assert len(est.series) >= 1


def test_estimate_load_synthetic_dense_trace_scores_high():
    """A dense trace + missed checkpoints + low mastery should score high."""
    est = estimate_load(
        trace_events=[
            {"opcode": "BEFORE_IF", "duration_ms": 5, "variables": {"x": 1}},
            {"opcode": "BEFORE_FOR", "duration_ms": 5, "variables": {"i": 0}},
            {"opcode": "BEFORE_WHILE", "duration_ms": 5, "variables": {}},
            {"opcode": "EXCEPTION", "duration_ms": 5, "variables": {}},
        ]
        * 3,
        interaction_events=[
            {"event_type": "tracer_pause", "metadata": {"duration_ms": 15000}},
            {"event_type": "tracer_pause", "metadata": {"duration_ms": 9000}},
            {"event_type": "tutor_checkpoint_miss", "metadata": {}},
        ],
        sm2_recent_events=[{"mastery_after": 0.1}],
    )
    assert est.score >= 60, f"Expected high load, got {est.score}"


def test_estimate_load_synthetic_simple_trace_scores_low():
    """A simple trace + no pauses + high mastery should score low."""
    est = estimate_load(
        trace_events=[
            {"opcode": "LINE", "duration_ms": 5, "variables": {"x": 1}},
        ],
        interaction_events=[],
        sm2_recent_events=[{"mastery_after": 0.95}],
    )
    assert est.score <= 30, f"Expected low load, got {est.score}"
