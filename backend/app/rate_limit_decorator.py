"""Shared rate-limit decorator for FastAPI endpoints (Workstream 10).

CogniTrace uses `slowapi` for per-process token-bucket rate limiting. The
limiter itself and the `_rate_limit` decorator used to live in
`app/routers/examples.py` and `app/routers/auth.py` — duplicated copies.
This module is the canonical home so every router imports from the same
place and a future Redis backend swap (Workstream 10 follow-up) only
needs to touch one file.

Usage:

    from app.rate_limit_decorator import _rate_limit

    @router.get("/dashboard")
    @_rate_limit("60/minute")
    async def get_dashboard(...):
        ...

If `slowapi` isn't installed (rare — it's in `pyproject.toml`), the
decorator degrades to a no-op so local dev still works. The CI environment
always has slowapi installed.

Collaborators:
    - `slowapi.Limiter` (the underlying library)
    - Called by every router under `app/routers/`.

Last significant change: Workstream 10 — promoted from a duplicated
copy in `examples.py` and `auth.py` into the shared module called out
by the hardening plan.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("cognitrace.rate_limit")


# ── Limiter (lazy-initialized) ─────────────────────────────────────

_limiter = None
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    _limiter = Limiter(key_func=get_remote_address)
except ImportError:
    logger.warning("slowapi_not_installed_rate_limiting_disabled")
    _limiter = None


# ── Decorator factory ──────────────────────────────────────────────


def _rate_limit(rate: str):
    """Apply a slowapi rate limit to a FastAPI route handler.

    Args:
        rate: A slowapi rate string, e.g. `"60/minute"`, `"20/minute"`,
              `"10/hour"`.

    Returns:
        A decorator that, when applied to an async endpoint function,
        enforces the given rate limit per remote address. If `slowapi`
        isn't installed, returns a no-op so the route still works.

    Example:
        >>> @router.get("/foo")
        >>> @_rate_limit("30/minute")
        >>> async def foo(...): ...
    """

    def decorator(func):
        if _limiter is None:
            return func
        return _limiter.limit(rate)(func)

    return decorator
