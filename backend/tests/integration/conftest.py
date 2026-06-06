import pytest
from unittest.mock import AsyncMock
from app.repositories.supabase import (
    SupabaseRepository,
    ProfileResult,
    TraceResult,
)

@pytest.fixture
def mock_supabase_repo():
    repo = AsyncMock(spec=SupabaseRepository)
    repo.get_profile_by_token = AsyncMock(return_value=ProfileResult(
        id="user-123", is_pro=False, email="test@example.com"
    ))
    repo.get_shared_trace = AsyncMock(return_value=TraceResult(
        id="trace-456",
        code="x = 1",
        steps=[{"step_number": 0, "line_number": 1, "variables": {}}],
        share_token="abc123",
        is_public=True,
        user_id="user-123",
        created_at="2025-01-01T00:00:00Z",
    ))
    repo.get_user_traces = AsyncMock(return_value=[])
    return repo


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset all slowapi rate limiter storages before each test to avoid test contamination."""
    limiters = []
    try:
        from app.main import app
        if hasattr(app.state, "limiter") and app.state.limiter:
            limiters.append(app.state.limiter)
    except Exception:
        pass

    try:
        from app.routers.traces import _limiter as traces_limiter
        if traces_limiter:
            limiters.append(traces_limiter)
    except Exception:
        pass

    try:
        from app.routers.examples import _limiter as examples_limiter
        if examples_limiter:
            limiters.append(examples_limiter)
    except Exception:
        pass

    try:
        from app.routers.auth import _limiter as auth_limiter
        if auth_limiter:
            limiters.append(auth_limiter)
    except Exception:
        pass

    for limiter in limiters:
        try:
            if hasattr(limiter, "_storage") and limiter._storage:
                limiter._storage.reset()
        except Exception:
            pass
