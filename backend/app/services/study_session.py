"""Pilot study session telemetry (Workstream W1 of the empirical study plan).

When the frontend sends `X-Study-Session: <uuid>` on any request, this module
makes that UUID available to service-layer code without explicit plumbing.
Backend code that wants to attach the session id to a downstream DB row
(e.g. an `llm_call_metrics` insert) reads it via `get_current_study_session_id()`.

When the header is absent (production traffic), the contextvar is empty and
the helper returns None. The instrumentation is therefore a zero-cost pass-through
for non-pilot traffic.

The associated database schema is in `backend/migrations/V013__study_sessions.sql`.
"""
from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger("cognitrace.study_session")

# ── Context-var holding the per-request study session UUID ─────────────────
# Set by `study_session_middleware` (main.py) when an inbound request carries
# the `X-Study-Session` header. Read by `get_current_study_session_id()`.
_study_session_id_var: ContextVar[Optional[str]] = ContextVar(
    "study_session_id", default=None
)

# ── Lightweight header validation ───────────────────────────────────────────
# The header is opaque to the application; the only client-generated value
# we accept is a UUID (RFC 4122 hex form). Anything else is ignored so a
# malformed or attacker-controlled header cannot poison the metrics table.
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_valid_study_session_id(value: str | None) -> bool:
    """Return True iff `value` is a syntactically valid UUID string."""
    if not value:
        return False
    return bool(_UUID_RE.match(value.strip()))


def get_current_study_session_id() -> str | None:
    """Return the current request's pilot study session UUID, or None.

    Backend code that writes telemetry rows (e.g. `llm_cache.store`,
    `llm_router.stream_explain`) should call this and pass the value through
    to Supabase so the row is FK-tagged with the session it belongs to.
    """
    return _study_session_id_var.get()


def bind_study_session_id(value: str | None) -> None:
    """Bind a study session UUID to the current request's context.

    Called by the HTTP middleware in `app/main.py`. Has no effect unless
    `value` is a valid UUID. The middleware always passes the result through,
    even when it's None, so production traffic doesn't break.
    """
    if is_valid_study_session_id(value):
        _study_session_id_var.set(value.strip())
    elif value is not None:
        # A malformed UUID was sent. Log once per *kind* of bad input to avoid spam.
        logger.warning(
            "invalid_study_session_header_dropped value=%r", value[:64]
        )
        _study_session_id_var.set(None)
    else:
        _study_session_id_var.set(None)
