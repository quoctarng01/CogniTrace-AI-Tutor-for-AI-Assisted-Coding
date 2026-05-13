"""Tests for FIX-MD-08: Dashboard streak hardcoded to 0."""
import inspect


def test_dashboard_uses_real_streak():
    """MEDIUM-08: Dashboard streak should come from _calculate_streak, not 0."""
    from app.routers.traces import get_dashboard
    
    source = inspect.getsource(get_dashboard)
    
    assert "streak=0" not in source, (
        "MEDIUM-08: Dashboard still has streak=0 hardcoded. "
        "Should call _calculate_streak from review.py."
    )
    assert "_calculate_streak" in source, (
        "MEDIUM-08: get_dashboard must import and call _calculate_streak."
    )
