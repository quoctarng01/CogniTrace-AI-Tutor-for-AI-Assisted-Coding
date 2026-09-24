"""Trace error → HTTP exception mapping.

Centralizes the HTTPException construction that used to live inside
`app/routers/traces.py`. Routers should import the helpers here rather than
construct HTTPException directly for trace-related errors.

Collaborators:
    - Called by every router under `app/routers/traces*`.
    - `FastAPI.HTTPException` is the only outbound dependency.

Last significant change: Workstream 2 — extracted from `app/routers/traces.py`.
"""
from __future__ import annotations

from fastapi import HTTPException


def side_effect_blocked_422(matched: list[str], warnings: list[str] | None = None) -> HTTPException:
    """422 returned when the static validator flags dangerous patterns."""
    return HTTPException(
        status_code=422,
        detail={
            "error": "SIDE_EFFECT_BLOCKED",
            "message": "This code contains patterns that are not allowed for security reasons.",
            "matched": matched,
            "warnings": warnings or [],
        },
    )


def timeout_408(message: str) -> HTTPException:
    return HTTPException(
        status_code=408,
        detail={"error": "TIMEOUT", "message": message},
    )


def syntax_error_422(message: str, line: int | None) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"error": "SYNTAX_ERROR", "message": message, "line": line},
    )


def max_steps_422(message: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"error": "MAX_STEPS", "message": message},
    )


def auth_required_401() -> HTTPException:
    return HTTPException(status_code=401, detail="Authentication required")


def trace_not_found_404() -> HTTPException:
    return HTTPException(status_code=404, detail="Trace not found")


def profile_not_found_404() -> HTTPException:
    return HTTPException(status_code=404, detail="User profile not found")


def upstream_failure_502(detail: str) -> HTTPException:
    """502 returned when the Supabase call returned non-2xx."""
    return HTTPException(status_code=502, detail=f"Upstream failure: {detail}")


def shared_trace_expired_410() -> HTTPException:
    return HTTPException(
        status_code=410,
        detail={
            "error": "EXPIRED",
            "message": "This trace has expired. Sign in to CogniTrace to view it.",
            "login_url": "/auth/login",
        },
    )
