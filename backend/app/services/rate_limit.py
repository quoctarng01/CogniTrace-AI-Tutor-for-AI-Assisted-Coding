"""
Redis-backed distributed rate limiter.
Falls back to in-memory implementation if Redis is unavailable.

Why Redis?
  - In-memory rate limiting (threading.Lock + dict) breaks on multi-instance
    Railway deployments: each instance has its own memory, so a user could
    get 2x the configured rate limit by hitting different instances.
  - Redis provides a single source of truth across all instances.
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger("codescope.rate_limit")

# ── Redis client (lazy, connected on first use) ────────────────────

_redis_client = None

def _get_redis():
    """Lazily initialize Redis connection."""
    global _redis_client
    if _redis_client is None and settings.redis_enabled:
        try:
            import redis.asyncio as redis
            _redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("redis_connected", extra={"url": settings.redis_url})
        except Exception as e:
            logger.warning("redis_connection_failed", extra={"error": str(e)})
            _redis_client = None
    return _redis_client


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_at: float
    retry_after_seconds: int = 0


# ── In-memory fallback (single-instance correctness only) ──────────

_inmemory_buckets: dict[str, tuple[int, float]] = {}


async def check_rate_limit_redis(key: str) -> RateLimitResult:
    """
    Check and update rate limit using Redis.
    
    Algorithm: Sliding window counter.
    Key format: rate_limit:{key} → stores JSON: {"count": N, "window_start": timestamp}
    
    Returns (allowed, remaining, reset_at, retry_after).
    """
    redis = _get_redis()
    if redis is None:
        return await check_rate_limit_inmemory(key)
    
    redis_key = f"rate_limit:{key}"
    window_seconds = settings.rate_limit_window_seconds
    limit = settings.rate_limit_per_hour
    now = time.time()
    now - window_seconds
    
    try:
        # Use a Lua script for atomic read-modify-write
        lua_script = """
        local key = KEYS[1]
        local limit = tonumber(ARGV[1])
        local window_seconds = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local window_start = now - window_seconds
        
        local data = redis.call('GET', key)
        local count = 0
        local ws = now
        
        if data then
            local parsed = cjson.decode(data)
            count = parsed.count or 0
            ws = parsed.window_start or now
            -- Reset if window has expired
            if ws < window_start then
                count = 0
                ws = now
            end
        end
        
        -- Check if already at limit
        if count >= limit then
            local retry_after = math.ceil(ws + window_seconds - now)
            return {0, 0, ws + window_seconds, retry_after}
        end
        
        -- Increment
        count = count + 1
        local new_data = cjson.encode({count = count, window_start = ws})
        redis.call('SET', key, new_data, 'EX', window_seconds * 2)
        
        return {1, limit - count, ws + window_seconds, 0}
        """
        
        result = await redis.eval(
            lua_script, 1,
            redis_key,
            str(limit),
            str(window_seconds),
            str(now),
        )
        
        allowed, remaining, reset_at, retry_after = result
        
        logger.debug(
            "rate_limit_check",
            key=key,
            allowed=bool(allowed),
            remaining=remaining,
        )
        
        return RateLimitResult(
            allowed=bool(allowed),
            remaining=remaining,
            reset_at=float(reset_at),
            retry_after_seconds=int(retry_after),
        )
        
    except Exception as e:
        logger.error("redis_rate_limit_error", extra={"error": str(e)})
        # Fallback to in-memory on Redis error
        return await check_rate_limit_inmemory(key)


async def check_rate_limit_inmemory(key: str) -> RateLimitResult:
    """
    In-memory fallback — only correct for single-instance deployments.
    WARNING: Does NOT work correctly with multiple Railway instances.
    """
    global _inmemory_buckets
    
    limit = settings.rate_limit_per_hour
    window_seconds = settings.rate_limit_window_seconds
    now = time.time()
    
    # Synchronize access (this is async but the dict is shared)
    count, window_start = _inmemory_buckets.get(key, (0, now))
    elapsed = now - window_start
    
    if elapsed >= window_seconds:
        # Window expired — reset
        _inmemory_buckets[key] = (1, now)
        return RateLimitResult(
            allowed=True,
            remaining=limit - 1,
            reset_at=now + window_seconds,
            retry_after_seconds=0,
        )
    
    if count >= limit:
        retry_after = int(window_seconds - elapsed)
        logger.warning(
            "rate_limit_exceeded_inmemory",
            extra={"key": key, "retry_after": retry_after, "note": "Multi-instance deployments may allow bypass — use Redis"},
        )
        return RateLimitResult(
            allowed=False,
            remaining=0,
            reset_at=window_start + window_seconds,
            retry_after_seconds=retry_after,
        )
    
    _inmemory_buckets[key] = (count + 1, window_start)
    
    return RateLimitResult(
        allowed=True,
        remaining=limit - count - 1,
        reset_at=window_start + window_seconds,
        retry_after_seconds=0,
    )


# ── Public API ────────────────────────────────────────────────────

async def check_rate_limit(key: str) -> RateLimitResult:
    """Check rate limit for a given key (IP address or user ID)."""
    return await check_rate_limit_redis(key)
