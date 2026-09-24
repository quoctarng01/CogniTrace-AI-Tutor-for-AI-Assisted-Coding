"""Unit tests for `app.services.errors` (Workstream 8).

These helpers are the only place that constructs HTTPException for
trace-related errors. Locking their contract down prevents subtle
status-code drift between routers.
"""
import pytest
from fastapi import HTTPException

from app.services import errors


@pytest.mark.parametrize(
    "fn, expected_status",
    [
        (lambda: errors.side_effect_blocked_422(["os.system"]), 422),
        (lambda: errors.timeout_408("took too long"), 408),
        (lambda: errors.syntax_error_422("bad", 3), 422),
        (lambda: errors.max_steps_422("step ceiling"), 422),
        (lambda: errors.auth_required_401(), 401),
        (lambda: errors.trace_not_found_404(), 404),
        (lambda: errors.profile_not_found_404(), 404),
        (lambda: errors.upstream_failure_502("supabase 5xx"), 502),
        (lambda: errors.shared_trace_expired_410(), 410),
    ],
)
def test_each_helper_returns_expected_status_code(fn, expected_status):
    """Every error helper returns an HTTPException with the documented status code."""
    exc = fn()
    assert isinstance(exc, HTTPException)
    assert exc.status_code == expected_status


def test_side_effect_blocked_payload_shape():
    """The side-effect-blocked payload includes matched patterns and warnings."""
    exc = errors.side_effect_blocked_422(["os.system", "subprocess.Popen"])
    detail = exc.detail
    assert detail["error"] == "SIDE_EFFECT_BLOCKED"
    assert "matched" in detail and detail["matched"] == ["os.system", "subprocess.Popen"]
    # Warnings default to [] when omitted
    assert detail["warnings"] == []


def test_side_effect_blocked_includes_warnings_when_provided():
    """Warnings are passed through when supplied."""
    exc = errors.side_effect_blocked_422(
        ["os.system"],
        warnings=["WARN_GLOBAL_STATE"],
    )
    assert exc.detail["warnings"] == ["WARN_GLOBAL_STATE"]


def test_syntax_error_payload_shape():
    """Syntax-error payload includes the offending line."""
    exc = errors.syntax_error_422("unexpected EOF", line=12)
    assert exc.detail["error"] == "SYNTAX_ERROR"
    assert exc.detail["line"] == 12
    assert "unexpected EOF" in exc.detail["message"]


def test_syntax_error_accepts_none_line():
    """When the parser cannot recover the line, `line` may be None."""
    exc = errors.syntax_error_422("invalid syntax", line=None)
    assert exc.detail["line"] is None


def test_shared_trace_expired_includes_login_url():
    """The 410 response includes a login URL so the client can recover."""
    exc = errors.shared_trace_expired_410()
    assert exc.detail["error"] == "EXPIRED"
    assert exc.detail["login_url"] == "/auth/login"


def test_upstream_failure_wraps_detail():
    """502 helper prefixes the detail with `Upstream failure:`."""
    exc = errors.upstream_failure_502("connection refused")
    assert "Upstream failure" in exc.detail
    assert "connection refused" in exc.detail
