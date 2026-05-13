"""
Concurrency limiter — prevents Railway instance from being overwhelmed.

Uses asyncio.Semaphore so requests queue in the async event loop
(no threads consumed while waiting) rather than blocking worker threads.
"""
from __future__ import annotations

import asyncio
import logging

from app.config import settings

logger = logging.getLogger("codescope.concurrency")

# ── Semaphore (one per worker process) ─────────────────────────────

TRACE_LIMIT = settings.max_concurrent_traces  # 25 per worker
_semaphore: asyncio.Semaphore | None = None

def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(TRACE_LIMIT)
    return _semaphore


async def run_with_concurrency_limit(coro_or_callable):
    """
    Run `coro_or_callable` only when a concurrency slot is available.
    Supports both async coroutines and sync callables.

    Usage:
        result = await run_with_concurrency_limit(run_trace(code))
        result = await run_with_concurrency_limit(some_async_coro())
    """
    import asyncio
    import inspect
    
    sem = _get_semaphore()
    async with sem:
        logger.debug("concurrency_slot_acquired", extra={"limit": TRACE_LIMIT})
        if inspect.iscoroutine(coro_or_callable):
            return await coro_or_callable
        else:
            # Sync callable — run in thread pool to avoid blocking event loop
            return await asyncio.to_thread(coro_or_callable)


class ConcurrencyLimiter:
    """
    Async context manager for concurrency-limited operations.
    
    Usage:
        limiter = ConcurrencyLimiter(limit=10)
        async with limiter:
            result = await some_async_operation()
    """
    
    def __init__(self, limit: int | None = None):
        self.limit = limit or TRACE_LIMIT
        self.sem = asyncio.Semaphore(self.limit)
        self._active = 0
    
    async def __aenter__(self):
        await self.sem.acquire()
        self._active += 1
        logger.debug("concurrency_slot_acquired", extra={"active": self._active, "limit": self.limit})
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._active -= 1
        self.sem.release()
        logger.debug("concurrency_slot_released", extra={"active": self._active, "limit": self.limit})
        return False  # Don't suppress exceptions
