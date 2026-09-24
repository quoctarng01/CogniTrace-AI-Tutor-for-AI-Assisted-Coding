"""Unit tests for `app.services.llm_cache`.

Workstream 8 — lock in the contract of the extracted cache module:

1. `ExplanationCache.get()` is a no-op when Supabase env vars are empty.
2. `ExplanationCache.get()` parses the Supabase RPC response correctly.
3. `ExplanationCache.store()` returns None (fire-and-forget) and never
   raises on errors (the router depends on this non-fatal contract).
4. `make_cache_key()` is deterministic and content-sensitive.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_cache import ExplanationCache, make_cache_key


# ──────────────────────────────────────────────────────────────────────
# make_cache_key
# ──────────────────────────────────────────────────────────────────────


def test_cache_key_is_deterministic():
    """Two calls with the same inputs must yield the same key."""
    k1 = make_cache_key("x = 1", 1, "x = 1", {"x": 1})
    k2 = make_cache_key("x = 1", 1, "x = 1", {"x": 1})
    assert k1 == k2


def test_cache_key_changes_with_locals():
    """Identical lines with different variable state must produce different keys.

    The cache is content-addressable, but if the locals vary between otherwise
    identical requests we must return different keys or we'd serve a
    stale explanation.
    """
    a = make_cache_key("x = 1", 1, "x = 1", {"x": 0})
    b = make_cache_key("x = 1", 1, "x = 1", {"x": 1})
    assert a != b


def test_cache_key_changes_with_line_number():
    """Different line numbers must produce different keys even for same code."""
    a = make_cache_key("x = 1\ny = 2", 1, "x = 1", {})
    b = make_cache_key("x = 1\ny = 2", 2, "y = 2", {})
    assert a != b


def test_cache_key_is_sha256_hex():
    """Cache key must be a 64-char hex string (SHA-256)."""
    key = make_cache_key("x = 1", 1, "x = 1", {})
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_cache_key_truncates_inputs():
    """Inputs longer than the truncation thresholds still produce stable keys."""
    long_code = "x = 1\n" + ("# comment\n" * 100)
    k = make_cache_key(long_code, 1, "x = 1" * 20, {"x": 1})
    k2 = make_cache_key(long_code + "# more", 1, "x = 1" * 20, {"x": 1})
    # First 200 chars of code are the same for these two inputs
    assert k == k2


# ──────────────────────────────────────────────────────────────────────
# ExplanationCache.get
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_returns_none_when_supabase_not_configured():
    """When Supabase env vars are empty, .get() short-circuits to None."""
    with patch("app.services.llm_cache.settings") as mock_settings:
        mock_settings.supabase_url = ""
        mock_settings.supabase_service_key = ""
        cache = ExplanationCache()
        result = await cache.get("any-key")
        assert result is None


@pytest.mark.asyncio
async def test_get_returns_explanation_text_on_success():
    """On a 200 with [{explanation_text: ...}], .get() returns the text."""
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"explanation_text": "This is the cached text."}]
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.llm_cache.settings") as mock_settings:
        mock_settings.supabase_url = "https://fake.supabase.co"
        mock_settings.supabase_service_key = "fake-key"

        cache = ExplanationCache(http=mock_http)
        result = await cache.get("any-key")

    assert result == "This is the cached text."


@pytest.mark.asyncio
async def test_get_returns_none_on_empty_response():
    """On 200 with an empty list, .get() returns None (cold cache)."""
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.llm_cache.settings") as mock_settings:
        mock_settings.supabase_url = "https://fake.supabase.co"
        mock_settings.supabase_service_key = "fake-key"

        cache = ExplanationCache(http=mock_http)
        result = await cache.get("any-key")

    assert result is None


@pytest.mark.asyncio
async def test_get_swallows_exceptions():
    """Network/JSON failures are logged but never bubble up."""
    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("app.services.llm_cache.settings") as mock_settings:
        mock_settings.supabase_url = "https://fake.supabase.co"
        mock_settings.supabase_service_key = "fake-key"

        cache = ExplanationCache(http=mock_http)
        # Must NOT raise
        result = await cache.get("any-key")

    assert result is None


# ──────────────────────────────────────────────────────────────────────
# ExplanationCache.store
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_is_noop_when_supabase_not_configured():
    """Without Supabase config, .store() does nothing (no HTTP call)."""
    with patch("app.services.llm_cache.settings") as mock_settings:
        mock_settings.supabase_url = ""
        mock_settings.supabase_service_key = ""
        cache = ExplanationCache()
        # Must complete without raising or calling HTTP
        await cache.store(
            cache_key="k",
            text="text",
            provider_used="ollama_cloud",
            model_name="llama3.2",
        )


@pytest.mark.asyncio
async def test_store_posts_to_supabase():
    """Successful .store() POSTs to /rest/v1/explanations with the right payload."""
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.text = "OK"
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.llm_cache.settings") as mock_settings:
        mock_settings.supabase_url = "https://fake.supabase.co"
        mock_settings.supabase_service_key = "fake-key"

        cache = ExplanationCache(http=mock_http)
        await cache.store(
            cache_key="my-key",
            text="explanation text",
            provider_used="ollama_cloud",
            model_name="llama3.2",
            line_number=42,
            trace_id="trace-uuid",
        )

    mock_http.post.assert_called_once()
    args, kwargs = mock_http.post.call_args
    # URL is the Supabase REST endpoint for the explanations table
    assert args[0] == "https://fake.supabase.co/rest/v1/explanations"
    body = kwargs["json"]
    assert body["cache_key"] == "my-key"
    assert body["explanation_text"] == "explanation text"
    assert body["model_used"] == "ollama_cloud"
    assert body["model_name"] == "llama3.2"
    assert body["cached"] is True
    assert body["line_number"] == 42
    assert body["trace_id"] == "trace-uuid"
    # The Prefer header for return=representation is required
    assert kwargs["headers"]["Prefer"] == "return=representation"


@pytest.mark.asyncio
async def test_store_swallows_http_errors():
    """A non-2xx response from Supabase must be logged but not raised."""
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal server error"
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.llm_cache.settings") as mock_settings:
        mock_settings.supabase_url = "https://fake.supabase.co"
        mock_settings.supabase_service_key = "fake-key"

        cache = ExplanationCache(http=mock_http)
        # Must NOT raise — failed cache writes are non-fatal
        await cache.store(
            cache_key="k",
            text="text",
            provider_used="ollama_cloud",
            model_name="llama3.2",
        )


@pytest.mark.asyncio
async def test_store_swallows_exceptions():
    """Any exception during .store() is logged but not raised."""
    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=RuntimeError("network down"))

    with patch("app.services.llm_cache.settings") as mock_settings:
        mock_settings.supabase_url = "https://fake.supabase.co"
        mock_settings.supabase_service_key = "fake-key"

        cache = ExplanationCache(http=mock_http)
        # Must NOT raise
        await cache.store(
            cache_key="k",
            text="text",
            provider_used="github_models",
            model_name="gpt-4o-mini",
        )


@pytest.mark.asyncio
async def test_store_accepts_optional_kwargs():
    """line_number / trace_id default to None and round-trip into the Supabase payload."""
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.text = "OK"
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.llm_cache.settings") as mock_settings:
        mock_settings.supabase_url = "https://fake.supabase.co"
        mock_settings.supabase_service_key = "fake-key"

        cache = ExplanationCache(http=mock_http)
        await cache.store(
            cache_key="k",
            text="text",
            provider_used="ollama_cloud",
            model_name="llama3.2",
            # NOTE: no line_number / trace_id passed
        )

    _, kwargs = mock_http.post.call_args
    assert kwargs["json"]["line_number"] is None
    assert kwargs["json"]["trace_id"] is None


# ──────────────────────────────────────────────────────────────────────
# V013 — pilot study session telemetry
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_forwards_study_session_id():
    """When the pilot middleware binds a UUID, `.store()` writes it into the JSON body."""
    import uuid as _uuid

    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.text = "OK"
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.llm_cache.settings") as mock_settings:
        mock_settings.supabase_url = "https://fake.supabase.co"
        mock_settings.supabase_service_key = "fake-key"

        cache = ExplanationCache(http=mock_http)
        session_uid = str(_uuid.uuid4())
        await cache.store(
            cache_key="k",
            text="text",
            provider_used="ollama_cloud",
            model_name="llama3.2",
            study_session_id=session_uid,
        )

    _, kwargs = mock_http.post.call_args
    assert kwargs["json"]["study_session_id"] == session_uid


@pytest.mark.asyncio
async def test_store_omits_study_session_id_when_not_provided():
    """Production traffic (no header) must not include the FK in the payload."""
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.text = "OK"
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.llm_cache.settings") as mock_settings:
        mock_settings.supabase_url = "https://fake.supabase.co"
        mock_settings.supabase_service_key = "fake-key"

        cache = ExplanationCache(http=mock_http)
        await cache.store(
            cache_key="k",
            text="text",
            provider_used="ollama_cloud",
            model_name="llama3.2",
            # NOTE: no study_session_id passed — backward-compatible default
        )

    _, kwargs = mock_http.post.call_args
    # The JSON body contains the field with a None value so the FK column is
    # explicitly null in Supabase (rather than relying on Supabase's default).
    assert kwargs["json"]["study_session_id"] is None
