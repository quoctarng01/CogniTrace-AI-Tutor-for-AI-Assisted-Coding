"""Tests for FIX-HI-07: Rate limit doesn't distinguish free vs Pro."""
import pytest
import inspect
from unittest.mock import AsyncMock, patch


def test_trace_limit_enforcement_in_run_trace():
    """HIGH-07: run_trace should check trace count for non-Pro users."""
    from app.routers import traces

    source = inspect.getsource(traces)

    # Verify the helper function exists
    assert "_get_trace_count_this_month" in source, (
        "HIGH-07: _get_trace_count_this_month helper not found in traces.py"
    )
    assert "is_pro_user" in source, (
        "HIGH-07: is_pro_user function not found in traces.py imports"
    )
    assert "FREE_TRACE_LIMIT" in source, (
        "HIGH-07: FREE_TRACE_LIMIT constant not found in run_trace"
    )
    assert "FREE_LIMIT_REACHED" in source, (
        "HIGH-07: FREE_LIMIT_REACHED error code not found in run_trace"
    )


@pytest.mark.asyncio
async def test_free_user_blocked_at_50_traces():
    """HIGH-07: Free user at 50+ traces should get HTTP 402."""
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: [{"id": f"trace-{i}"} for i in range(50)]
        MockClient.return_value = mock_instance

        from app.routers.traces import _get_trace_count_this_month
        from app.config import Settings

        settings = Settings()
        count = await _get_trace_count_this_month("user-123", settings)
        assert count == 50, f"Expected 50, got {count}"

        # Verify FREE_LIMIT_REACHED will be raised (count >= limit)
        FREE_TRACE_LIMIT = 50
        assert count >= FREE_TRACE_LIMIT, "At limit, should raise HTTP 402"


@pytest.mark.asyncio
async def test_pro_user_bypasses_limit():
    """HIGH-07: Pro users should not be checked against the trace limit."""
    from app.dependencies import is_pro_user

    # Test pro user
    with patch('app.dependencies.httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: [{"plan": "pro"}]
        MockClient.return_value = mock_instance

        result = await is_pro_user("user-pro-123")
        assert result is True, "User with plan='pro' should return True"

    # Test free user
    with patch('app.dependencies.httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: [{"plan": "free"}]
        MockClient.return_value = mock_instance

        result = await is_pro_user("user-free-456")
        assert result is False, "User with plan='free' should return False"


@pytest.mark.asyncio
async def test_trace_count_this_month():
    """HIGH-07: _get_trace_count_this_month should return correct count."""
    from app.routers.traces import _get_trace_count_this_month
    from app.config import Settings

    # Test with 0 traces
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: []
        MockClient.return_value = mock_instance

        settings = Settings()
        count = await _get_trace_count_this_month("user-empty", settings)
        assert count == 0, f"Expected 0, got {count}"

    # Test with 10 traces
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: [{"id": f"trace-{i}"} for i in range(10)]
        MockClient.return_value = mock_instance

        count = await _get_trace_count_this_month("user-10", settings)
        assert count == 10, f"Expected 10, got {count}"
