"""Unit tests for httpx client reuse — FIX-CR-02."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_llm_router_reuses_http_client():
    """Verify LLMRouter uses self._http for cache operations, not creating new clients."""
    from app.services.llm_router import LLMRouter
    
    router = LLMRouter()
    
    # Mock self._http
    mock_http = MagicMock()
    mock_http.post = AsyncMock()
    mock_http.post.return_value.status_code = 200
    mock_http.post.return_value.json.return_value = []
    router._http = mock_http
    
    # Call _get_cached twice
    await router._get_cached("test_key")
    await router._get_cached("test_key2")
    
    # CRITICAL: Should be 2 post calls (reusing self._http)
    # If using new httpx.AsyncClient() per call, this would fail
    assert mock_http.post.call_count == 2, (
        f"Expected 2 post calls via self._http, got {mock_http.post.call_count}. "
        "CRITICAL-02: Methods must use self._http, not create new clients per request."
    )


@pytest.mark.asyncio
async def test_store_cached_uses_self_http():
    """Verify _store_cached uses self._http, not creating new clients."""
    from app.services.llm_router import LLMRouter
    
    router = LLMRouter()
    
    # Mock self._http
    mock_http = MagicMock()
    mock_http.post = AsyncMock()
    mock_http.post.return_value.status_code = 201
    router._http = mock_http
    
    # Call _store_cached
    await router._store_cached(
        cache_key="test_key",
        text="test explanation",
        provider_used="github_models",
        model_name="gpt-4o-mini",
    )
    
    # Verify self._http.post was called
    assert mock_http.post.call_count == 1
    # Verify Prefer header is return=representation (FIX-CR-04)
    call_kwargs = mock_http.post.call_args.kwargs
    assert call_kwargs.get('headers', {}).get('Prefer') == 'return=representation'
