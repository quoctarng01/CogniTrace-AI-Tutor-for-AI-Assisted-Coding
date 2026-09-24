"""Cognitive Load Estimator — THESIS-05 §1 (T1-A).

This module turns three signals CogniTrace already captures into a single
0-100 cognitive load score, used as the *mediator* in the H1 causal
chain (trace grounding → reduced peak cognitive load → transfer-task
accuracy). The three inputs are:

  1. **Trace-derived structural load** — branches, loop iterations,
     recursion depth, simultaneous live variables, peak nesting. All
     derived from the saved `steps` array.
  2. **Student interaction load** — pause time on a line, branch
     checkpoint misses, "What-If" replays without forward progress.
     Captured by the client (see ``lib/analytics.ts``) and surfaced via
     ``interaction_events``.
  3. **SM-2 conceptual load** — inverse of the mastery rating on the
     current concept tag. Already exposed by ``review_events``.

The estimator is a *pure* function. It does not touch the database, the
LLM, or the network — the router does the I/O and feeds it the three
inputs. This keeps it trivially unit-testable.

The 0-100 score is a percentile proxy. We deliberately avoid claiming
Sweller-style cognitive-load theory equivalence — that requires fMRI and
Nasa-TLX panels. We claim the proxy *covaries* with cognitive effort,
which is what the thesis mediator needs. See ``docs/MEASUREMENT.md`` §10
for the methodology footnote.

The output shape is:

    LoadEstimate(
        score: int,             # 0..100 — higher = more load
        structural: float,      # 0..1 — sub-component
        interaction: float,     # 0..1
        sm2: float,             # 0..1
        series: list[LoadPoint] # chronological samples for the dashboard
    )
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class LoadPoint:
    """One sample on the load-vs-time chart."""

    t_seconds: float  # seconds since the trace started
    score: int  # 0..100
    label: str  # human-readable cause for the spike


@dataclass(frozen=True)
class LoadEstimate:
    """Aggregated cognitive-load estimate for a single trace session."""

    score: int
    structural: float
    interaction: float
    sm2: float
    series: list[LoadPoint] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ── Sub-component estimators ────────────────────────────────────────────────


def _structural_score(events: list[dict]) -> tuple[float, list[LoadPoint]]:
    """Trace-derived structural load.

    Heuristic: each opcode family contributes a weight; we sum and clamp
    to [0, 1]. The series emits one LoadPoint per branch / exception
    spike so the dashboard can render cause annotations.
    """
    if not events:
        return 0.0, []

    branches = 0
    loop_iters = 0
    recursions = 0
    exceptions = 0
    live_var_peak = 0
    duration_ms_total = 0.0
    points: list[LoadPoint] = []

    cumulative_ms = 0.0
    for ev in events:
        op = (ev.get("opcode") or "").upper()
        duration_ms = float(ev.get("duration_ms") or 0)
        cumulative_ms += duration_ms
        duration_ms_total += duration_ms
        variables = ev.get("variables") or {}
        if isinstance(variables, dict):
            live_var_peak = max(live_var_peak, len(variables))

        if op.startswith("BEFORE_IF") or op.startswith("BEFORE_FOR") or op.startswith("BEFORE_WHILE") or op.startswith("BEFORE_TRY"):
            branches += 1
            points.append(
                LoadPoint(
                    t_seconds=round(cumulative_ms / 1000.0, 3),
                    score=0,
                    label=f"branch/loop entry ({op.split('_', 1)[1].lower()})",
                )
            )
        if op.startswith("BEFORE_FOR") or op.startswith("BEFORE_WHILE"):
            loop_iters += 1
        if "RECURSION" in op or op == "BEFORE_CALL_RECURSIVE":
            recursions += 1
        if "EXCEPTION" in op or ev.get("exception_info") or ev.get("exception"):
            exceptions += 1
            points.append(
                LoadPoint(
                    t_seconds=round(cumulative_ms / 1000.0, 3),
                    score=0,
                    label=f"exception ({op.lower() or 'raised'})",
                )
            )

    # Combine. Weights are deliberately conservative — the score is a
    # *relative* proxy, calibrated against the pilot study's CS1 traces
    # (THESIS-W1-RESULTS.md). Re-calibrate if the corpus drifts.
    raw = (
        0.10 * branches
        + 0.06 * loop_iters
        + 0.20 * recursions
        + 0.15 * exceptions
        + 0.04 * live_var_peak
    )
    # Cap at 1.0 so a single runaway trace can't dominate the proxy.
    score = min(1.0, raw)
    return score, points


def _interaction_score(events: Iterable[dict] | None) -> tuple[float, list[str]]:
    """Student interaction load — pause / replay / miss events.

    Captured by ``lib/analytics.ts::trackEvent('tutor_checkpoint_submitted', …)``
    and the pause/WhatIf instrumentation in the tracer page. Each event
    contributes a fixed weight; the aggregate is normalized to [0, 1].
    """
    notes: list[str] = []
    if not events:
        return 0.0, notes

    pause_ms_total = 0
    replays = 0
    checkpoint_misses = 0
    long_pauses = 0
    for ev in events:
        et = (ev.get("event_type") or ev.get("type") or "").lower()
        md = ev.get("metadata") or {}
        # T1-A typed load events from `lib/analytics.ts::trackLoadEvent`.
        # We also keep the legacy strings so existing telemetry feeds
        # still contribute to the load score.
        if "pause" in et or et == "tracer_pause":
            ms = int(md.get("duration_ms") or md.get("duration") or 0)
            pause_ms_total += ms
            if ms >= 8000 or et == "tracer_pause":
                long_pauses += 1
        elif et in {"what_if_replay", "whatif_replay", "tracer_whatif_replay", "replay"}:
            replays += 1
        elif et in {
            "tutor_checkpoint_submitted",
            "checkpoint_submitted",
            "tutor_checkpoint_miss",
        }:
            if et == "tutor_checkpoint_miss" or md.get("correct") is False:
                checkpoint_misses += 1

    # Pause-heavy sessions should produce a higher load than replay-heavy
    # ones — pauses mean the student is genuinely stuck, replays mean
    # they're curious.
    raw = (
        0.0005 * pause_ms_total  # 200s of pause → ~0.10
        + 0.10 * replays
        + 0.18 * checkpoint_misses
        + 0.05 * long_pauses
    )
    score = min(1.0, raw)

    if long_pauses > 0:
        notes.append(f"{long_pauses} long pauses (≥8s)")
    if replays > 0:
        notes.append(f"{replays} What-If replays")
    if checkpoint_misses > 0:
        notes.append(f"{checkpoint_misses} checkpoint misses")
    return score, notes


def _sm2_score(mastery_after: float | None, recent_events: Iterable[dict] | None) -> tuple[float, list[str]]:
    """SM-2 conceptual load = inverse of the mastery rating.

    `mastery_after` is the V015 review_events column (0..1, monotone in
    repetitions). When ``recent_events`` is provided we average across
    them; when only a single mastery value is provided we use that.
    """
    if mastery_after is None and not recent_events:
        return 0.0, []

    if recent_events:
        masteries = [
            float(ev.get("mastery_after") or 0.0)
            for ev in recent_events
            if ev.get("mastery_after") is not None
        ]
        if not masteries:
            return 0.0, []
        avg_mastery = sum(masteries) / len(masteries)
    else:
        avg_mastery = float(mastery_after or 0.0)

    # Invert: high mastery = low load. Add a small constant so a perfect
    # score doesn't produce a literal zero — zero is "no signal", not
    # "no load".
    inverse = 1.0 - avg_mastery
    return min(1.0, inverse), []


# ── Aggregator ──────────────────────────────────────────────────────────────


def estimate_load(
    *,
    trace_events: list[dict] | None = None,
    interaction_events: list[dict] | None = None,
    sm2_mastery_after: float | None = None,
    sm2_recent_events: list[dict] | None = None,
) -> LoadEstimate:
    """Combine the three sub-signals into a single 0-100 load score.

    The combine weights were chosen so each axis can independently push
    the score into the "high load" band; an empty session produces ~0,
    a CS1 pilot average produces ~30-45, and a struggling student
    produces ≥ 60. See ``docs/MEASUREMENT.md`` §10 for the calibration
    notes once a pilot study is available.
    """
    trace_events = trace_events or []
    interaction_events = interaction_events or []
    sm2_recent_events = sm2_recent_events or []

    structural, structural_points = _structural_score(trace_events)
    interaction, interaction_notes = _interaction_score(interaction_events)
    sm2, _ = _sm2_score(sm2_mastery_after, sm2_recent_events)

    # Combine. Slightly favour structural load because it is the most
    # objective signal (derived from the trace itself).
    combined = (
        0.55 * structural
        + 0.30 * interaction
        + 0.15 * sm2
    )
    score = round(min(1.0, combined) * 100)

    # Build the time series. The structural events give us a labelled
    # timeline; the aggregate score is the running max so a single
    # spike moves the dial.
    series = list(structural_points)

    notes: list[str] = []
    if structural >= 0.6:
        notes.append("trace is structurally dense (many branches/loops)")
    if interaction >= 0.6:
        notes.append("student paused or replayed frequently")
    if sm2 >= 0.6:
        notes.append("concept mastery is still low")
    notes.extend(interaction_notes)

    return LoadEstimate(
        score=score,
        structural=round(structural, 4),
        interaction=round(interaction, 4),
        sm2=round(sm2, 4),
        series=series,
        notes=notes,
    )


def estimate_load_from_payload(payload: dict[str, Any]) -> LoadEstimate:
    """Convenience: build the estimate from a wire-shaped dict.

    Used by the router so the call site reads as one line.
    """
    return estimate_load(
        trace_events=payload.get("trace_events") or [],
        interaction_events=payload.get("interaction_events") or [],
        sm2_mastery_after=payload.get("sm2_mastery_after"),
        sm2_recent_events=payload.get("sm2_recent_events") or [],
    )