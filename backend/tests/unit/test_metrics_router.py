"""Unit tests for `app.routers.metrics` (Workstream 10).

These tests cover the window-parser helper and the response shape.
They do *not* exercise the Supabase round-trip — that's covered by
integration tests against a live DB.
"""
import pytest
from fastapi import HTTPException

from app.routers.metrics import _parse_window


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1d", 1),
        ("7d", 7),
        ("30d", 30),
        ("90d", 90),
    ],
)
def test_parse_window_accepts_valid_inputs(raw, expected):
    """Valid `Nd` strings parse to the expected integer."""
    assert _parse_window(raw) == expected


def test_parse_window_defaults_to_7d_on_empty():
    """Empty / falsy input falls back to 7 days."""
    assert _parse_window("") == 7
    assert _parse_window(None) == 7  # type: ignore[arg-type]


@pytest.mark.parametrize("raw", ["7", "7h", "abc", "d", "-1d", "0d"])
def test_parse_window_rejects_invalid_inputs(raw):
    """Anything that doesn't match `Nd` (with N >= 1) raises 422."""
    with pytest.raises(HTTPException) as exc_info:
        _parse_window(raw)
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"] == "INVALID_WINDOW"


def test_parse_window_caps_at_90_days():
    """The endpoint enforces a 90-day ceiling so a malicious client can't OOM us."""
    with pytest.raises(HTTPException):
        _parse_window("91d")
