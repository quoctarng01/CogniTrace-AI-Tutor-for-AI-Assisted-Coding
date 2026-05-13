# File: backend/tests/unit/test_examples.py
# Tests for the examples router. Run with: python -m pytest tests/unit/test_examples.py -v

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import Response

from app.routers.examples import (
    list_examples,
    get_example,
    save_example_to_queue,
    _parse_annotations,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_row():
    """Raw Supabase row as dict."""
    return {
        "id": "c4e00001-0000-0000-0000-000000000001",
        "category": "comprehensions",
        "title": "Nested comprehension",
        "code": "result = [[x for x in row if x > 0] for row in matrix if any(y > 0 for y in row)]",
        "why_ai_generates_this": "AI nests comprehensions for two-level filtering.",
        "annotations": '[{"line":1,"text":"outer comprehension iterates rows","type":"iterator"}]',
        "explanation": "The outer comprehension iterates each row. Rows with no positive values are skipped.",
        "common_mistakes": ["Confusing if belongs to which level"],
        "review_interval": "1,3,7,14",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


# ── Test: _parse_annotations ─────────────────────────────────────────────────

def test_parse_annotations_from_json_string(sample_row):
    """JSON string annotations are parsed into Annotation objects."""
    anns = _parse_annotations(sample_row["annotations"])
    assert len(anns) == 1
    assert anns[0].line == 1
    assert anns[0].type == "iterator"
    assert anns[0].text == "outer comprehension iterates rows"


def test_parse_annotations_from_list():
    """List annotations are parsed directly without JSON decoding."""
    anns = _parse_annotations([{"line": 2, "text": "inner filter", "type": "filter"}])
    assert len(anns) == 1
    assert anns[0].type == "filter"


def test_parse_annotations_empty():
    """Empty/None annotations return empty list."""
    assert _parse_annotations(None) == []
    assert _parse_annotations([]) == []
    assert _parse_annotations("") == []


# ── Test: list_examples ──────────────────────────────────────────────────────

def _mock_client(*responses):
    """Build httpx AsyncClient mock returning responses in order."""
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    mock.get = AsyncMock(side_effect=list(responses))
    mock.post = AsyncMock(side_effect=list(responses))
    return mock


@pytest.fixture
def mock_request():
    """Minimal Starlette Request stub that satisfies slowapi."""
    from starlette.requests import Request
    m = MagicMock(spec=Request)
    m.headers = {}
    m.client = MagicMock(host="127.0.0.1")
    return m


@pytest.mark.asyncio
async def test_list_examples_returns_records(sample_row):
    """GET /examples returns example records with parsed annotations and total count."""
    mock = _mock_client(
        Response(200, json=[sample_row], headers={"content-range": "0-0/25"}),
        Response(200, headers={"content-range": "0-24/25"}),
    )
    with patch("app.routers.examples.httpx.AsyncClient", return_value=mock):
        from starlette.requests import Request
        result = await list_examples(request=MagicMock(spec=Request), category=None, limit=20, offset=0)

    assert len(result.examples) == 1
    assert result.examples[0].title == "Nested comprehension"
    assert result.examples[0].category == "comprehensions"
    assert len(result.examples[0].annotations) == 1
    assert result.total == 25


@pytest.mark.asyncio
async def test_list_examples_filters_by_category(sample_row, mock_request):
    """GET /examples?category=comprehensions sends category filter to Supabase."""
    mock = _mock_client(
        Response(200, json=[sample_row], headers={"content-range": "0-0/5"}),
        Response(200, headers={"content-range": "0-4/5"}),
    )
    with patch("app.routers.examples.httpx.AsyncClient", return_value=mock):
        result = await list_examples(request=mock_request, category="comprehensions", limit=20, offset=0)

    assert result.examples[0].category == "comprehensions"


@pytest.mark.asyncio
async def test_list_examples_pagination(sample_row):
    """GET /examples respects limit and offset parameters."""
    mock = _mock_client(
        Response(200, json=[sample_row], headers={"content-range": "0-9/25"}),
        Response(200, headers={"content-range": "0-9/25"}),
    )
    with patch("app.routers.examples.httpx.AsyncClient", return_value=mock):
        from starlette.requests import Request
        result = await list_examples(request=MagicMock(spec=Request), category=None, limit=10, offset=10)

    assert result.limit == 10
    assert result.offset == 10


# ── Test: get_example ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_example_returns_annotations(sample_row):
    """GET /examples/{id} returns parsed annotations."""
    mock = _mock_client(Response(200, json=[sample_row]))
    with patch("app.routers.examples.httpx.AsyncClient", return_value=mock):
        from starlette.requests import Request
        result = await get_example(request=MagicMock(spec=Request), example_id=sample_row["id"])

    assert result.title == "Nested comprehension"
    assert len(result.annotations) == 1
    assert result.annotations[0].type == "iterator"
    assert result.annotations[0].line == 1


@pytest.mark.asyncio
async def test_get_example_not_found():
    """GET /examples/{id} returns 404 when example does not exist."""
    mock = _mock_client(Response(200, json=[]))
    with patch("app.routers.examples.httpx.AsyncClient", return_value=mock):
        from starlette.requests import Request
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_example(request=MagicMock(spec=Request), example_id="nonexistent")
        assert exc_info.value.status_code == 404


# ── Test: save_example_to_queue ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_requires_auth(mock_request):
    """POST /examples/{id}/save without auth returns 401."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await save_example_to_queue(
            example_id="c4e00001-0000-0000-0000-000000000001",
            req=None,
            authorization=None,
            request=mock_request,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_save_free_plan(sample_row, mock_request):
    """POST /examples/{id}/save with free plan returns 403."""
    with patch("app.routers.examples.get_current_user", return_value={"id": "user-1"}), \
         patch("app.routers.examples._fetch_profile", return_value={"plan": "free"}), \
         patch("app.routers.examples.get_profile_id", return_value="profile-1"):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await save_example_to_queue(
                example_id=sample_row["id"],
                req=None,
                authorization="Bearer mock-token",
                request=mock_request,
            )
        assert exc_info.value.status_code == 403
        assert "UPGRADE_REQUIRED" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_save_creates_trace_and_card(sample_row, mock_request):
    """POST with pro plan and no existing card creates trace+card and returns 201."""
    httpx_mock = _mock_client(Response(200, json=[sample_row]))  # fetches the example
    with patch("app.routers.examples.get_current_user", return_value={"id": "user-1"}), \
         patch("app.routers.examples.get_profile_id", return_value="profile-1"), \
         patch("app.routers.examples._fetch_profile", return_value={"plan": "pro"}), \
         patch("app.routers.examples._check_existing_card", return_value=None), \
         patch("app.routers.examples._get_or_create_trace", return_value="trace-abc"), \
         patch("app.routers.examples._create_review_card", return_value="card-xyz"), \
         patch("app.routers.examples.httpx.AsyncClient", return_value=httpx_mock):
        result = await save_example_to_queue(
            example_id=sample_row["id"],
            req=None,
            authorization="Bearer mock-token",
            request=mock_request,
        )

    assert result.existing is False
    assert result.card_id == "card-xyz"


@pytest.mark.asyncio
async def test_save_duplicate_returns_existing(sample_row, mock_request):
    """POST when card already exists returns 200 with existing card_id."""
    httpx_mock = _mock_client(Response(200, json=[sample_row]))  # fetches the example
    with patch("app.routers.examples.get_current_user", return_value={"id": "user-1"}), \
         patch("app.routers.examples.get_profile_id", return_value="profile-1"), \
         patch("app.routers.examples._fetch_profile", return_value={"plan": "pro"}), \
         patch("app.routers.examples._check_existing_card", return_value="existing-card-123"), \
         patch("app.routers.examples.httpx.AsyncClient", return_value=httpx_mock):
        result = await save_example_to_queue(
            example_id=sample_row["id"],
            req=None,
            authorization="Bearer mock-token",
            request=mock_request,
        )

    assert result.existing is True
    assert result.card_id == "existing-card-123"
    assert "Already in your review queue" in result.message


@pytest.mark.asyncio
async def test_save_example_not_found(mock_request):
    """POST with nonexistent example_id returns 404."""
    httpx_mock = _mock_client(Response(200, json=[]))  # no rows returned
    with patch("app.routers.examples.get_current_user", return_value={"id": "user-1"}), \
         patch("app.routers.examples.get_profile_id", return_value="profile-1"), \
         patch("app.routers.examples._fetch_profile", return_value={"plan": "pro"}), \
         patch("app.routers.examples.httpx.AsyncClient", return_value=httpx_mock):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await save_example_to_queue(
                example_id="nonexistent-id-xyz",
                req=None,
                authorization="Bearer mock-token",
                request=mock_request,
            )
        assert exc_info.value.status_code == 404
