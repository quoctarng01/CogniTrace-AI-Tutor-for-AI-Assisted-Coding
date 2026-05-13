"""Unit tests for streak calculation — FIX-HI-02."""
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_calculate_streak_consecutive_days():
    """HI-02: _calculate_streak should return consecutive days count, not card count."""
    from app.routers.review import _calculate_streak
    
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    two_days_ago = (today - timedelta(days=2)).isoformat()
    four_days_ago = (today - timedelta(days=4)).isoformat()
    
    # Simulate 3 consecutive days: today, yesterday, two_days_ago
    mock_cards = [
        {"last_reviewed_at": today.isoformat()},
        {"last_reviewed_at": yesterday},
        {"last_reviewed_at": two_days_ago},
        {"last_reviewed_at": four_days_ago},  # Gap on day 3
    ]
    
    # httpx Response.json() is synchronous
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=mock_cards)
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)
    
    with patch('app.routers.review.httpx.AsyncClient', return_value=mock_client):
        streak = await _calculate_streak("user-123", "https://test.supabase.co", "key")
        
        assert streak == 3, (
            f"HI-02: streak returned {streak}, expected 3. "
            "Streak should count consecutive days, not card count."
        )


@pytest.mark.asyncio
async def test_calculate_streak_gap_resets():
    """A gap in review days should reset the streak count."""
    from app.routers.review import _calculate_streak
    
    today = date.today()
    two_days_ago = (today - timedelta(days=2)).isoformat()  # Gap yesterday
    
    mock_cards = [
        {"last_reviewed_at": today.isoformat()},
        {"last_reviewed_at": two_days_ago},  # No yesterday = streak of 1
    ]
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=mock_cards)
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)
    
    with patch('app.routers.review.httpx.AsyncClient', return_value=mock_client):
        streak = await _calculate_streak("user-123", "https://test.supabase.co", "key")
        
        assert streak == 1, (
            f"HI-02: gap should reset streak to 1, got {streak}"
        )
