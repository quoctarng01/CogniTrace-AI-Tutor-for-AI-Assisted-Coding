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
