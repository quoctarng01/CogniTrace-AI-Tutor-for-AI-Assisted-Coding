"""End-to-end tests for `GET /api/load/trace/{trace_id}` (T1-A).

The endpoint composes three signals:
  * trace events from `traces.steps` (via the Supabase repo)
  * interaction events from `anonymous_events` (via an httpx fetch)
  * SM-2 review events from `review_events` (via an httpx fetch)

The Supabase repo is monkeypatched via `app.dependency_overrides`.
The httpx fetches are mocked by patching the module-level helper
functions (`_fetch_interaction_events`, `_fetch_sm2_recent`) so the
test runs offline.

These tests prove:
  * the endpoint requires auth (401)
  * a loaded trace returns the expected 0..100 + sub-scores + series
  * 404 when the trace doesn't exist
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_supabase_repo
from app.main import app


TRACE_ID = "trace-load-test"
USER_ID = "user-load-test"


@pytest.fixture
def load_repo():
    """Fake repo with one trace and a few steps that should yield a low
    structural load."""
    repo = AsyncMock()
    fake_traces = {
        TRACE_ID: {
            "id": TRACE_ID,
            "code": "def f(): pass",
            "steps": [
                {"opcode": "LINE", "duration_ms": 10, "variables": {"x": 1}},
            ],
            "user_id": USER_ID,
            "concept_tags": ["FUNCTION"],
            "is_public": False,
        }
    }

    async def _get(path, params=None, **kwargs):
        if "/rest/v1/traces" in path:
            p = params or {}
            if p.get("id"):
                tid = p["id"].removeprefix("eq.")
                t = fake_traces.get(tid)
                return [t] if t else []
        return []

    repo._get = _get
    app.dependency_overrides[get_supabase_repo] = lambda: repo
    yield repo
    app.dependency_overrides.pop(get_supabase_repo, None)


@pytest.fixture
def client(load_repo):
    return TestClient(app)


# ── Auth gate ────────────────────────────────────────────────────


def test_load_requires_auth(client):
    """The endpoint must 401 without an Authorization header."""
    resp = client.get(f"/api/load/trace/{TRACE_ID}")
    assert resp.status_code == 401


def test_load_rejects_non_bearer(client):
    resp = client.get(
        f"/api/load/trace/{TRACE_ID}",
        headers={"Authorization": "Token x"},
    )
    assert resp.status_code == 401


# ── Happy path ───────────────────────────────────────────────────


def test_load_returns_estimate_for_existing_trace(client):
    """With one simple step and no interaction / sm2 events, score should be low."""
    with patch(
        "app.routers.load._fetch_interaction_events",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.routers.load._fetch_sm2_recent",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.routers.auth.get_current_user",
        new=AsyncMock(return_value={"id": USER_ID}),
    ), patch(
        "app.routers.load.get_profile_id_for_user",
        new=AsyncMock(return_value=USER_ID),
    ):
        resp = client.get(
            f"/api/load/trace/{TRACE_ID}",
            headers={"Authorization": "Bearer test-token"},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["trace_id"] == TRACE_ID
    assert 0 <= payload["score"] <= 100
    assert 0.0 <= payload["structural"] <= 1.0
    assert 0.0 <= payload["interaction"] <= 1.0
    assert 0.0 <= payload["sm2"] <= 1.0
    assert isinstance(payload["series"], list)
    assert payload["primary_concept_tag"] == "FUNCTION"
    assert payload["events_count"]["trace_steps"] == 1
    assert payload["events_count"]["interaction_events"] == 0
    assert payload["events_count"]["sm2_events"] == 0


def test_load_returns_high_score_for_dense_trace(client):
    """A dense trace + pauses + checkpoint misses should produce a high score."""
    dense_steps = [
        {"opcode": "BEFORE_IF", "duration_ms": 5, "variables": {"x": 1}},
        {"opcode": "BEFORE_FOR", "duration_ms": 5, "variables": {"i": 0}},
        {"opcode": "EXCEPTION", "duration_ms": 5, "variables": {}},
    ]
    interaction_events = [
        {"event_type": "tracer_pause", "metadata": {"duration_ms": 15000}},
        {"event_type": "tutor_checkpoint_miss", "metadata": {}},
    ]
    sm2_events = [{"mastery_after": 0.2}]

    # Replace the trace in the repo with a dense one
    client.app.dependency_overrides[get_supabase_repo]()._get = AsyncMock(
        return_value=[
            {
                "id": TRACE_ID,
                "code": "def g(): ...",
                "steps": dense_steps,
                "user_id": USER_ID,
                "concept_tags": ["LOOP"],
                "is_public": False,
            }
        ]
    )

    with patch(
        "app.routers.load._fetch_interaction_events",
        new=AsyncMock(return_value=interaction_events),
    ), patch(
        "app.routers.load._fetch_sm2_recent",
        new=AsyncMock(return_value=sm2_events),
    ), patch(
        "app.routers.auth.get_current_user",
        new=AsyncMock(return_value={"id": USER_ID}),
    ), patch(
        "app.routers.load.get_profile_id_for_user",
        new=AsyncMock(return_value=USER_ID),
    ):
        resp = client.get(
            f"/api/load/trace/{TRACE_ID}",
            headers={"Authorization": "Bearer test-token"},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["score"] >= 50, f"expected high load, got {payload['score']}"
    assert payload["primary_concept_tag"] == "LOOP"
    assert len(payload["series"]) >= 1
    # At least one note should mention pauses or misses
    assert any("pause" in n or "miss" in n or "mastery" in n for n in payload["notes"])


# ── 404 path ─────────────────────────────────────────────────────


def test_load_404_when_trace_missing(client):
    with patch(
        "app.routers.load._fetch_interaction_events",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.routers.load._fetch_sm2_recent",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.routers.auth.get_current_user",
        new=AsyncMock(return_value={"id": USER_ID}),
    ), patch(
        "app.routers.load.get_profile_id_for_user",
        new=AsyncMock(return_value=USER_ID),
    ):
        resp = client.get(
            "/api/load/trace/trace-does-not-exist",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 404
