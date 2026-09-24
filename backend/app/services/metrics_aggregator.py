"""Daily-aggregation job that materialises `llm_call_metrics_daily`.

Workstream 10 — keeps the dashboard endpoint fast and the SQL cheap.

Design notes:
- The rollup is read by `GET /api/metrics/cache-hit-rate` (the dashboard
  page makes the call on every render), so we want it pre-computed.
- We compute one (day, provider) row per UTC day, regardless of when
  the row was originally created. That keeps the aggregation idempotent:
  re-running it for "yesterday" produces the same numbers as the first
  time we did it.
- The job is hooked into FastAPI's startup hook via `app.main.startup`.
  For multi-instance deployments, the production swap is a `pg_cron`
  schedule — see `docs/MEASUREMENT.md` §5.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

import httpx

from app.config import settings

logger = logging.getLogger("cognitrace.metrics_aggregator")


# The SQL is intentionally not parameterised — it's a hard-coded daily
# rollup that runs against Postgres-managed Supabase. We never substitute
# user input into it.
_ROLLUP_SQL = """
INSERT INTO llm_call_metrics_daily (
    day,
    provider,
    cache_hit_rate,
    p50_latency_ms,
    p95_latency_ms,
    total_calls,
    total_input_tokens,
    total_output_tokens,
    updated_at
)
SELECT
    date_trunc('day', created_at)::date AS day,
    provider,
    ROUND(
        100.0 * SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END)::numeric
        / NULLIF(COUNT(*), 0)::numeric,
        2
    ) AS cache_hit_rate,
    COALESCE(
        percentile_disc(0.5) WITHIN GROUP (ORDER BY latency_ms) FILTER (WHERE NOT cache_hit),
        0
    )::int AS p50_latency_ms,
    COALESCE(
        percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms) FILTER (WHERE NOT cache_hit),
        0
    )::int AS p95_latency_ms,
    COUNT(*)::int AS total_calls,
    COALESCE(SUM(input_tokens), 0)::bigint AS total_input_tokens,
    COALESCE(SUM(output_tokens), 0)::bigint AS total_output_tokens,
    NOW() AS updated_at
FROM llm_call_metrics
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY 1, 2
ON CONFLICT (day, provider) DO UPDATE SET
    cache_hit_rate = EXCLUDED.cache_hit_rate,
    p50_latency_ms = EXCLUDED.p50_latency_ms,
    p95_latency_ms = EXCLUDED.p95_latency_ms,
    total_calls = EXCLUDED.total_calls,
    total_input_tokens = EXCLUDED.total_input_tokens,
    total_output_tokens = EXCLUDED.total_output_tokens,
    updated_at = NOW();
"""


async def run_once(client: httpx.AsyncClient | None = None) -> int:
    """Run the rollup once. Returns the number of rows touched (0 on error).

    Acquires its own client if none is passed — useful for the
    startup-time first-run where no shared client exists yet.
    """
    if not settings.supabase_url or not settings.supabase_service_key:
        logger.info("rollup_skipped supabase_not_configured")
        return 0

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=30.0)

    try:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/rpc/run_sql",
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "Content-Type": "application/json",
            },
            json={"query": _ROLLUP_SQL},
        )
        if resp.status_code != 200:
            logger.warning("rollup_failed status=%d body=%s", resp.status_code, resp.text[:200])
            return 0
        logger.info("rollup_ok")
        return 1
    except Exception as e:
        logger.warning("rollup_error err=%s", e)
        return 0
    finally:
        if own_client:
            await client.aclose()


async def run_periodically(interval_seconds: int = 3600) -> None:
    """Long-running task: run the rollup every `interval_seconds`.

    The first run happens ~30 seconds after startup (giving Postgres time
    to be ready); subsequent runs happen on the interval.
    """
    await asyncio.sleep(30)
    while True:
        try:
            await run_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("rollup_loop_error err=%s", e)
        await asyncio.sleep(interval_seconds)
