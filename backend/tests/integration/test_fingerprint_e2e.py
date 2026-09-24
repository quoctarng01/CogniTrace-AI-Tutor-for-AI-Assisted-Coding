"""End-to-end fingerprint pipeline.

Exercises the read-side surface (router + classifier + repo) end-to-end:

  1. Pre-seed a fake trace in the mock repo
  2. GET /api/traces/{id}/fingerprint        → JSON wire payload
  3. GET /api/fingerprint/{share_token}      → JSON via token
  4. GET /fingerprint/{share_token}/card.svg → SVG OG card
  5. Lazy backfill: traces saved before V014 get a fingerprint on first GET

The Supabase layer is monkeypatched via FastAPI dependency_overrides so the
test runs offline. Everything else — fingerprint classification, AST walker,
SVG rendering, wire-format serialisation, lazy compute — runs for real.

The save-side stamping (the classifier being called inside POST /api/traces)
is covered by `tests/unit/test_fingerprint.py` against the same sample code.
Hooking the auth + validator chain of /api/traces here would require a full
JWT mock and is out of scope for this regression net.

This is the regression net for thesis Contribution #4.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_supabase_repo
from app.main import app
from app.repositories.supabase import FingerprintResult
from app.services.fingerprint import compute_fingerprint


# ── Sample code ────────────────────────────────────────────────────

# Same B04_mutation_iter snippet the unit tests use — known branches=2,
# peak nesting 3 → YELLOW.
SAMPLE_CODE = (
    "def remove_negatives(nums):\n"
    "    for num in nums:\n"
    "        if num < 0:\n"
    "            nums.remove(num)\n"
    "    return nums\n"
    "\n"
    "print(remove_negatives([1, -2, 3, -4, 5]))\n"
)

SAMPLE_STEPS = [
    {"step_number": i, "line_number": 1, "variables": {}, "branches_taken": {}}
    for i in range(12)
]

TRACE_ID = "trace-fp-e2e"
SHARE_TOKEN = "fp-share-token-e2e"
USER_ID = "user-fp-e2e"


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def fp_repo():
    """A fake SupabaseRepository wired to the three fingerprint methods + a
    fake traces table keyed by share_token for the OG-card lookup path."""
    repo = AsyncMock()
    stored_fps: dict[str, FingerprintResult] = {}
    fake_traces: dict[str, dict] = {
        TRACE_ID: {
            "id": TRACE_ID,
            "code": SAMPLE_CODE,
            "steps": SAMPLE_STEPS,
            "user_id": USER_ID,
            "share_token": SHARE_TOKEN,
            "is_public": True,
            "created_at": "2026-01-01T00:00:00Z",
        }
    }

    async def upsert_fingerprint(*, trace_id, user_id, payload):
        row = FingerprintResult(
            id="row-fp-e2e",
            trace_id=trace_id,
            user_id=user_id,
            json=payload,
            compact=payload["compact"],
            short_form=payload["short"],
            signature=payload["signature"],
            branches=payload["branches"],
            recursion_depth=payload["recursion_depth"],
            loop_iterations=payload["loop_iterations"],
            total_steps=payload["total_steps"],
            conceptual_complexity=payload["conceptual_complexity"],
            total_duration_ms=payload["total_duration_ms"],
            exception_types=list(payload["exception_types"]),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        stored_fps[trace_id] = row
        return row

    async def get_fingerprint_by_trace_id(trace_id):
        return stored_fps.get(trace_id)

    async def get_fingerprint_by_share_token(share_token, owner_id=None):
        # Join via fake traces table — same shape as the real implementation.
        trace = next(
            (t for t in fake_traces.values() if t.get("share_token") == share_token),
            None,
        )
        if not trace:
            return None
        if not trace.get("is_public") and trace.get("user_id") != owner_id:
            return None
        return stored_fps.get(trace["id"])

    repo.upsert_fingerprint = upsert_fingerprint
    repo.get_fingerprint_by_trace_id = get_fingerprint_by_trace_id
    repo.get_fingerprint_by_share_token = get_fingerprint_by_share_token

    async def _get(path, params=None, **kwargs):
        if "/rest/v1/traces" in path:
            p = params or {}
            if p.get("id"):
                tid = p["id"].removeprefix("eq.")
                t = fake_traces.get(tid)
                return [t] if t else []
            if p.get("share_token"):
                tok = p["share_token"].removeprefix("eq.")
                t = next((t for t in fake_traces.values() if t.get("share_token") == tok), None)
                if not t:
                    return []
                if p.get("is_public") == "eq.true" and not t.get("is_public"):
                    return []
                return [t]
        return []

    repo._get = _get
    repo._fake_traces = fake_traces
    repo._stored_fps = stored_fps

    app.dependency_overrides[get_supabase_repo] = lambda: repo
    yield repo
    app.dependency_overrides.pop(get_supabase_repo, None)


@pytest.fixture
def client(fp_repo):
    return TestClient(app)


# ── Tests ──────────────────────────────────────────────────────────


def test_fingerprint_json_endpoint_returns_wire_payload(fp_repo, client):
    """After stamping, GET /api/traces/{id}/fingerprint returns the canonical wire shape."""
    # Pre-stamp a fingerprint the way the save flow would.
    fp = compute_fingerprint(SAMPLE_CODE, SAMPLE_STEPS)
    fp_repo._stored_fps[TRACE_ID] = FingerprintResult(
        id="row-fp-e2e",
        trace_id=TRACE_ID,
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

    resp = client.get(f"/traces/{TRACE_ID}/fingerprint")
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    # The 10 wire-format fields are all present
    for key in (
        "compact",
        "short",
        "signature",
        "branches",
        "recursion_depth",
        "loop_iterations",
        "total_steps",
        "conceptual_complexity",
        "exception_types",
        "total_duration_ms",
    ):
        assert key in payload, f"missing wire field: {key}"

    # Classifier ran for real — sanity-check shape.
    assert payload["compact"].startswith("◆B")
    assert isinstance(payload["signature"], str) and len(payload["signature"]) >= 8
    assert payload["conceptual_complexity"] in ("🟢", "🟡", "🔴")
    # B04_mutation_iter has 1 for + 1 if → branches=2, peak nesting 3 → YELLOW
    assert payload["branches"] == 2
    assert payload["conceptual_complexity"] == "🟡"


def test_fingerprint_share_token_endpoint_matches_by_id(fp_repo, client):
    """GET /api/fingerprint/{share_token} returns the same payload as the by-id endpoint."""
    fp = compute_fingerprint(SAMPLE_CODE, SAMPLE_STEPS)
    fp_repo._stored_fps[TRACE_ID] = FingerprintResult(
        id="row-fp-e2e",
        trace_id=TRACE_ID,
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

    by_id = client.get(f"/traces/{TRACE_ID}/fingerprint").json()
    by_token = client.get(f"/api/fingerprint/{SHARE_TOKEN}").json()

    assert by_id["compact"] == by_token["compact"]
    assert by_id["signature"] == by_token["signature"]
    assert by_id["branches"] == by_token["branches"] == 2


def test_fingerprint_og_card_is_valid_svg(fp_repo, client):
    """GET /fingerprint/{share_token}/card.svg returns an SVG card with the canonical marker."""
    fp = compute_fingerprint(SAMPLE_CODE, SAMPLE_STEPS)
    fp_repo._stored_fps[TRACE_ID] = FingerprintResult(
        id="row-fp-e2e",
        trace_id=TRACE_ID,
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

    resp = client.get(f"/fingerprint/{SHARE_TOKEN}/card.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    body = resp.text
    assert "<svg" in body and "</svg>" in body
    assert "◆" in body  # the canonical marker
    # B04_mutation_iter — expect at least one of the metric markers to appear
    assert any(tag in body for tag in ("B2", "R0", "LO1", "T"))


def test_fingerprint_og_card_etag_round_trip(fp_repo, client):
    """If-None-Match against the ETag should yield 304 — the second fetch is free."""
    fp = compute_fingerprint(SAMPLE_CODE, SAMPLE_STEPS)
    fp_repo._stored_fps[TRACE_ID] = FingerprintResult(
        id="row-fp-e2e",
        trace_id=TRACE_ID,
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

    first = client.get(f"/fingerprint/{SHARE_TOKEN}/card.svg")
    assert first.status_code == 200
    etag = first.headers.get("etag")
    assert etag is not None
    second = client.get(f"/fingerprint/{SHARE_TOKEN}/card.svg", headers={"If-None-Match": etag})
    assert second.status_code == 304


def test_fingerprint_lazy_compute_backfills_missing_rows(fp_repo, client):
    """A trace with no fingerprint row yet (saved before V014) gets one on first GET."""
    # No fingerprint row exists for TRACE_ID yet — but the trace itself does.
    assert TRACE_ID not in fp_repo._stored_fps

    resp = client.get(f"/traces/{TRACE_ID}/fingerprint")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["compact"].startswith("◆B")
    assert payload["signature"]

    # The fingerprint row must have been written as a side effect.
    assert TRACE_ID in fp_repo._stored_fps
    assert fp_repo._stored_fps[TRACE_ID].compact == payload["compact"]


def test_fingerprint_og_card_lazy_compute_too(fp_repo, client):
    """OG card endpoint also lazy-computes — covers traces that were
    only stamped through the share-token path."""
    assert TRACE_ID not in fp_repo._stored_fps
    resp = client.get(f"/fingerprint/{SHARE_TOKEN}/card.svg")
    assert resp.status_code == 200
    assert TRACE_ID in fp_repo._stored_fps


def test_fingerprint_endpoints_404_when_trace_missing(fp_repo, client):
    """Both endpoints 404 cleanly when the trace itself doesn't exist."""
    missing_trace = "trace-does-not-exist-123"
    missing_token = "missing-token-123"

    assert client.get(f"/traces/{missing_trace}/fingerprint").status_code == 404
    assert client.get(f"/api/fingerprint/{missing_token}").status_code == 404
    assert client.get(f"/fingerprint/{missing_token}/card.svg").status_code == 404
