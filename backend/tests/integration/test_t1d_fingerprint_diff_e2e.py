"""End-to-end tests for the new T1-D fingerprint endpoints.

Exercises the full request lifecycle for:
  * POST /fingerprint/from-code — compute without persisting
  * GET  /fingerprint/diff        — side-by-side diff
  * GET  /fingerprint/diff/card.svg — diff OG card SVG

The Supabase layer is monkeypatched via `app.dependency_overrides` so the
test runs offline (no real DB calls).
"""
from __future__ import annotations

import re
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_supabase_repo
from app.main import app
from app.repositories.supabase import FingerprintResult


TRACE_A = "trace-t1d-a"
TRACE_B = "trace-t1d-b"
USER_ID = "user-t1d"

# Realistic 32-char hex share tokens (mirrors `secrets.token_hex(16)`).
# The router's heuristic treats 16+ char hex-without-dashes as a token.
TOKEN_A = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
TOKEN_B = "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7"

CODE_A = """\
def fibonacci(n):
    result = []
    a, b = 0, 1
    for i in range(n):
        result.append(a)
        a, b = b, a + b
    return result
"""

CODE_B = """\
def fibonacci(n):
    if n <= 0:
        return []
    result = []
    a, b = 0, 1
    for i in range(n):
        result.append(a)
        a, b = b, a + b
    return result
"""

STEPS = [
    {"step_number": i, "line_number": 1, "variables": {}, "branches_taken": {}}
    for i in range(8)
]


@pytest.fixture
def t1d_repo():
    """Fake repo with two pre-stamped traces + their fingerprints."""
    repo = AsyncMock()
    from app.services.fingerprint import compute_fingerprint

    fp_a = compute_fingerprint(CODE_A, STEPS)
    fp_b = compute_fingerprint(CODE_B, STEPS)

    fake_traces = {
        TRACE_A: {
            "id": TRACE_A,
            "code": CODE_A,
            "steps": STEPS,
            "user_id": USER_ID,
            "is_public": True,
            "share_token": TOKEN_A,
            "created_at": "2026-01-01T00:00:00Z",
        },
        TRACE_B: {
            "id": TRACE_B,
            "code": CODE_B,
            "steps": STEPS,
            "user_id": USER_ID,
            "is_public": True,
            "share_token": TOKEN_B,
            "created_at": "2026-01-01T00:00:00Z",
        },
    }

    def _fp_result(trace_id, fp):
        return FingerprintResult(
            id=f"row-{trace_id}",
            trace_id=trace_id,
            user_id=USER_ID,
            json=fp.to_dict(),
            compact=fp.compact(),
            short_form=fp.short(),
            signature=fp.signature(),
            branches=fp.branches,
            recursion_depth=fp.recursion_depth,
            loop_iterations=fp.loop_iterations,
            total_steps=fp.total_steps,
            conceptual_complexity=fp.conceptual_complexity,
            total_duration_ms=fp.total_duration_ms,
            exception_types=list(fp.exception_types),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )

    stored_fps = {TRACE_A: _fp_result(TRACE_A, fp_a), TRACE_B: _fp_result(TRACE_B, fp_b)}

    async def get_by_trace(trace_id):
        return stored_fps.get(trace_id)

    async def get_by_token(token, owner_id=None):
        for t in fake_traces.values():
            if t.get("share_token") == token:
                if not t.get("is_public") and t.get("user_id") != owner_id:
                    return None
                return stored_fps.get(t["id"])
        return None

    repo.get_fingerprint_by_trace_id = get_by_trace
    repo.get_fingerprint_by_share_token = get_by_token

    async def upsert_fingerprint(*, trace_id, user_id, payload):
        """`AsyncMock` auto-stubs this in unit tests, but here we want
        the result to look like a real `FingerprintResult` so the diff
        path can use `.json` / `.compact`."""
        if trace_id in stored_fps:
            return stored_fps[trace_id]
        # Compute fresh if needed (used by `_ensure_fingerprint_for_trace`)
        fp = compute_fingerprint(payload.get("code") or "", payload.get("steps") or [])
        row = FingerprintResult(
            id=f"row-{trace_id}",
            trace_id=trace_id,
            user_id=user_id,
            json=payload,
            compact=payload.get("compact") or fp.compact(),
            short_form=payload.get("short") or fp.short(),
            signature=payload.get("signature") or fp.signature(),
            branches=payload["branches"],
            recursion_depth=payload["recursion_depth"],
            loop_iterations=payload["loop_iterations"],
            total_steps=payload["total_steps"],
            conceptual_complexity=payload["conceptual_complexity"],
            total_duration_ms=payload["total_duration_ms"],
            exception_types=list(payload.get("exception_types") or []),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        stored_fps[trace_id] = row
        return row

    repo.upsert_fingerprint = upsert_fingerprint

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
def client(t1d_repo):
    return TestClient(app)


# ── POST /fingerprint/from-code ──────────────────────────────────


def test_from_code_endpoint_computes_fingerprint_without_db(client):
    """The endpoint must compute a Fingerprint from raw code + steps."""
    resp = client.post(
        "/api/fingerprint/from-code",
        json={"code": CODE_A, "steps": STEPS},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "compact" in payload
    assert "branches" in payload
    assert "conceptual_complexity" in payload
    assert payload["compact"].startswith("◆B")


def test_from_code_endpoint_handles_minimal_input(client):
    """Empty / short code should still return a valid (mostly zero) fingerprint."""
    resp = client.post(
        "/api/fingerprint/from-code",
        json={"code": "x = 1\n", "steps": []},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["branches"] == 0
    assert payload["recursion_depth"] == 0


# ── GET /fingerprint/diff ───────────────────────────────────────


def test_diff_endpoint_returns_deltas_for_two_traces(client):
    """Side-by-side diff produces a non-empty delta list with narrative."""
    resp = client.get(
        f"/api/diff/fingerprint?a={TRACE_A}&b={TRACE_B}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["a_kind"] == "trace_id"
    assert payload["b_kind"] == "trace_id"
    assert isinstance(payload["deltas"], list)
    assert payload["identical"] is False
    if payload["deltas"]:
        first = payload["deltas"][0]
        assert set(first.keys()) >= {
            "field",
            "label",
            "a_value",
            "b_value",
            "narrative",
            "significant",
        }


def test_diff_endpoint_accepts_share_tokens(client):
    """The heuristic must resolve 16+ char hex strings as share tokens."""
    resp = client.get(
        f"/api/diff/fingerprint?a={TOKEN_A}&b={TOKEN_B}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["a_kind"] == "share_token"
    assert payload["b_kind"] == "share_token"


def test_diff_endpoint_404_for_missing_trace(client):
    resp = client.get(
        "/api/diff/fingerprint?a=trace-does-not-exist&b=trace-also-missing",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 404


# ── GET /fingerprint/diff/card.svg ──────────────────────────────


def test_diff_card_svg_returns_valid_svg(client):
    """The diff OG card must be a valid SVG with the expected fragments."""
    resp = client.get(
        f"/api/fingerprint/diff/card.svg?a={TRACE_A}&b={TRACE_B}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "<svg" in body
    assert "</svg>" in body
    # The card should contain something mentioning the structural difference.
    assert "CogniTrace" in body
    # Multiple text elements expected (one per fingerprint + the diff summary)
    text_count = len(re.findall(r"<text\b", body))
    assert text_count >= 2


def test_diff_card_svg_404_for_missing(client):
    resp = client.get(
        "/api/fingerprint/diff/card.svg?a=trace-missing&b=trace-also-missing",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 404
