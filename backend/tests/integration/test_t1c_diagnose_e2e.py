"""End-to-end tests for `/api/llm/diagnose` with checkpoint_mode (T1-C).

Exercises the request lifecycle of the diagnose endpoint with the
T1-C extensions:

  * `concept_tag` field on the request → triggers selector lookup
  * `checkpoint_mode` field → forces a specific mode (override path)
  * response carries `checkpoint_mode` + `checkpoint_mode_rationale` +
    optional `hint` (scaffolded / contrastive only)

The LLM router is patched at module level (`app.routers.llm.llm_router`)
so the test runs offline. The auth path is mocked the same way as
`test_diagnose.py`.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _fake_diagnosis() -> dict:
    return {
        "tag": "loop_off_by_one",
        "explanation": "Loop runs N-1 times instead of N.",
        # Hint field is filled by the LLM when the system prompt is
        # scaffolded/contrastive; we simulate that here.
        "hint": "Try counting what happens when i equals n-1.",
    }


# ── Direct mode (default) ────────────────────────────────────────


def test_diagnose_returns_direct_when_no_concept_tag(client):
    """No concept_tag → selector returns DIRECT."""
    req = {
        "code": "x = 5",
        "checkpoint_type": "variable_prediction",
        "variable_name": "x",
        "correct_value": "5",
        "user_prediction": "0",
        "line_number": 1,
    }
    with patch(
        "app.routers.llm.llm_router.diagnose_misconception",
        new=AsyncMock(return_value=_fake_diagnosis()),
    ) as mock_diag:
        resp = client.post("/api/llm/diagnose", json=req)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkpoint_mode"] == "direct"
    # In direct mode the hint field isn't surfaced (still present in the
    # underlying diagnosis, but the API contract omits it).
    assert body.get("hint") is None
    # The mock should have been called with checkpoint_mode="direct".
    _, kwargs = mock_diag.call_args
    assert kwargs["checkpoint_mode"] == "direct"


# ── Override path ────────────────────────────────────────────────


def test_diagnose_respects_explicit_checkpoint_mode(client):
    """Setting `checkpoint_mode` + `override_mode=true` should bypass the selector."""
    req = {
        "code": "x = 5",
        "checkpoint_type": "variable_prediction",
        "variable_name": "x",
        "correct_value": "5",
        "user_prediction": "0",
        "line_number": 1,
        "concept_tag": "loop_off_by_one",
        "checkpoint_mode": "contrastive",
        "override_mode": True,
    }
    with patch(
        "app.routers.llm.llm_router.diagnose_misconception",
        new=AsyncMock(return_value=_fake_diagnosis()),
    ) as mock_diag:
        resp = client.post("/api/llm/diagnose", json=req)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkpoint_mode"] == "contrastive"
    # Override path uses rationale = "client_provided"
    assert body["checkpoint_mode_rationale"] == "client_provided"
    _, kwargs = mock_diag.call_args
    assert kwargs["checkpoint_mode"] == "contrastive"


# ── Selector path ────────────────────────────────────────────────


def test_diagnose_selects_scaffolded_on_one_recent_miss(client):
    """One miss in the recent window → selector returns SCAFFOLDED."""
    now = datetime.now(timezone.utc)
    events = [
        {"rating": "again", "occurred_at": (now - timedelta(days=1)).isoformat(), "concept_tag": "LOOP"},
    ]
    # Mock the fetch_recent_concept_reviews helper to return our events.
    fake_review_resp = MagicMock()
    fake_review_resp.status_code = 200
    fake_review_resp.json = MagicMock(return_value=events)

    fake_post = MagicMock()
    fake_post.status_code = 201
    fake_post.json = MagicMock(return_value=[{"id": "trace-uuid"}])

    fake_get_ctx = MagicMock()
    fake_get_ctx.__aenter__ = AsyncMock(return_value=fake_get_ctx)
    fake_get_ctx.__aexit__ = AsyncMock(return_value=None)
    fake_get_ctx.get = AsyncMock(return_value=fake_review_resp)
    fake_get_ctx.post = AsyncMock(return_value=fake_post)

    req = {
        "code": "for i in range(n): total += i",
        "checkpoint_type": "loop_iteration",
        "variable_name": "total",
        "correct_value": "sum_1_to_n",
        "user_prediction": "sum_0_to_n_minus_1",
        "line_number": 1,
        "concept_tag": "LOOP",
    }
    with patch(
        "app.routers.llm.llm_router.diagnose_misconception",
        new=AsyncMock(return_value=_fake_diagnosis()),
    ) as mock_diag, patch(
        "app.routers.llm.httpx.AsyncClient",
        return_value=fake_get_ctx,
    ):
        resp = client.post(
            "/api/llm/diagnose",
            json=req,
            headers={"Authorization": "Bearer test-token"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkpoint_mode"] == "scaffolded"
    assert "_miss_in_last_" in body["checkpoint_mode_rationale"]
    # The hint should be present in the response
    assert body.get("hint") is not None
    _, kwargs = mock_diag.call_args
    assert kwargs["checkpoint_mode"] == "scaffolded"


def test_diagnose_selects_contrastive_on_two_recent_misses(client):
    """Two+ misses in the recent window → selector returns CONTRASTIVE."""
    now = datetime.now(timezone.utc)
    events = [
        {"rating": "again", "occurred_at": (now - timedelta(days=0)).isoformat(), "concept_tag": "LOOP"},
        {"rating": "again", "occurred_at": (now - timedelta(days=1)).isoformat(), "concept_tag": "LOOP"},
    ]
    fake_review_resp = MagicMock()
    fake_review_resp.status_code = 200
    fake_review_resp.json = MagicMock(return_value=events)

    fake_post = MagicMock()
    fake_post.status_code = 201
    fake_post.json = MagicMock(return_value=[{"id": "trace-uuid"}])

    fake_get_ctx = MagicMock()
    fake_get_ctx.__aenter__ = AsyncMock(return_value=fake_get_ctx)
    fake_get_ctx.__aexit__ = AsyncMock(return_value=None)
    fake_get_ctx.get = AsyncMock(return_value=fake_review_resp)
    fake_get_ctx.post = AsyncMock(return_value=fake_post)

    req = {
        "code": "for i in range(n): total += i",
        "checkpoint_type": "loop_iteration",
        "variable_name": "total",
        "correct_value": "sum_1_to_n",
        "user_prediction": "sum_0_to_n_minus_1",
        "line_number": 1,
        "concept_tag": "LOOP",
    }
    with patch(
        "app.routers.llm.llm_router.diagnose_misconception",
        new=AsyncMock(return_value=_fake_diagnosis()),
    ) as mock_diag, patch(
        "app.routers.llm.httpx.AsyncClient",
        return_value=fake_get_ctx,
    ):
        resp = client.post(
            "/api/llm/diagnose",
            json=req,
            headers={"Authorization": "Bearer test-token"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkpoint_mode"] == "contrastive"
    assert body.get("hint") is not None


# ── Hint field only present in non-direct modes ──────────────────


def test_diagnose_hint_only_returned_when_mode_adapts(client):
    """When mode is direct, the hint field is omitted from the response."""
    req = {
        "code": "x = 1",
        "checkpoint_type": "variable_prediction",
        "variable_name": "x",
        "correct_value": "1",
        "user_prediction": "0",
        "line_number": 1,
        # No concept_tag → DIRECT
    }
    with patch(
        "app.routers.llm.llm_router.diagnose_misconception",
        new=AsyncMock(return_value=_fake_diagnosis()),
    ):
        resp = client.post("/api/llm/diagnose", json=req)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkpoint_mode"] == "direct"
    # The underlying diagnosis has a hint, but the response contract
    # omits it in direct mode (the frontend uses the presence of a
    # mode badge to decide whether to show the hint UI).
    assert body.get("hint") is None
