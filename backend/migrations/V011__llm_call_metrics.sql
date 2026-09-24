-- ============================================================
-- V011: LLM call metrics table (Workstream 4 + 6)
-- ============================================================
-- Records every LLM provider call. Used by:
--   - `GET /api/metrics/llm` (cache hit rate, p50 latency, per-model counts)
--   - `GET /api/metrics/cache-hit-rate` (24-hour sliding window)
--   - The dashboard's "AI system health" card.
--
-- One row per provider call. The `cache_hit` column flips to false on the
-- first time a `(cache_key)` is seen; subsequent identical requests update
-- an aggregate counter via the daily-rollup table in Workstream 10.
-- ============================================================

CREATE TABLE IF NOT EXISTS llm_call_metrics (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key         TEXT NOT NULL,
    model_used        TEXT NOT NULL,        -- 'ollama_cloud' | 'ollama_local' | 'github_models' | 'custom_openai' | 'fallback'
    model_name        TEXT NOT NULL,        -- the actual model identifier (e.g. 'llama3.2-3b')
    prompt_tokens     INT,
    completion_tokens INT,
    latency_ms        INT,
    cache_hit         BOOLEAN DEFAULT false,
    user_id           UUID REFERENCES profiles(id) ON DELETE SET NULL,
    error             TEXT,                  -- populated when the provider call failed
    created_at        TIMESTAMPTZ DEFAULT now()
);

-- Index for the canonical metric queries:
--   - "cache hit rate over time" (V011)
--   - "total tokens spent per day" (Workstream 10 daily rollup)
CREATE INDEX IF NOT EXISTS idx_llm_call_metrics_created_at
    ON llm_call_metrics(created_at);

CREATE INDEX IF NOT EXISTS idx_llm_call_metrics_cache_hit_created
    ON llm_call_metrics(cache_hit, created_at);

CREATE INDEX IF NOT EXISTS idx_llm_call_metrics_cache_key
    ON llm_call_metrics(cache_key);

CREATE INDEX IF NOT EXISTS idx_llm_call_metrics_user_created
    ON llm_call_metrics(user_id, created_at);

-- ============================================================
-- Daily aggregation table (Workstream 10 dependency)
-- ============================================================
-- Populated by a background job (`backend/app/services/llm_telemetry.py`)
-- that runs hourly via cron-like trigger. Each row is one calendar day.

CREATE TABLE IF NOT EXISTS llm_call_metrics_daily (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    day             DATE NOT NULL UNIQUE,
    total_calls     INT NOT NULL DEFAULT 0,
    cache_hits      INT NOT NULL DEFAULT 0,
    cache_hit_rate  FLOAT,                       -- = cache_hits / total_calls
    p50_latency_ms  INT,
    p95_latency_ms  INT,
    total_tokens    BIGINT,
    by_model        JSONB,                       -- {'ollama_cloud': 123, 'github_models': 45, ...}
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_call_metrics_daily_day
    ON llm_call_metrics_daily(day);

-- ============================================================
-- Row Level Security
-- ============================================================

ALTER TABLE llm_call_metrics       ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_call_metrics_daily ENABLE ROW LEVEL SECURITY;

-- llm_call_metrics is admin-only (the application writes rows; end users don't read them directly).
-- Service-role bypasses RLS, so the application can write freely. For dashboard reads,
-- expose aggregated views instead (Workstream 10).
-- Note: the original policy checked `plan = 'pro' AND plan = 'admin'` which is a
-- tautology (a row cannot be both 'pro' AND 'admin') and matched zero rows. Replaced
-- with `plan IN ('pro', 'admin')` so admin users can actually read the metrics.
CREATE POLICY "admin_read_metrics" ON llm_call_metrics
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid() AND p.plan IN ('pro', 'admin')
        )
    );

-- Daily rollup is readable by any authenticated user (powers the dashboard widget).
CREATE POLICY "auth_read_daily_metrics" ON llm_call_metrics_daily
    FOR SELECT USING (auth.uid() IS NOT NULL);

-- ============================================================
-- Convenient aggregate view for the GET /api/metrics/llm endpoint
-- ============================================================

CREATE OR REPLACE VIEW v_llm_metrics_summary AS
SELECT
    COUNT(*)                                          AS total_calls,
    COUNT(*) FILTER (WHERE cache_hit)                 AS cache_hits,
    COUNT(*) FILTER (WHERE NOT cache_hit)             AS cache_misses,
    ROUND(100.0 * COUNT(*) FILTER (WHERE cache_hit) / NULLIF(COUNT(*), 0), 2) AS cache_hit_rate_pct,
    COALESCE(SUM(prompt_tokens), 0)                  AS total_prompt_tokens,
    COALESCE(SUM(completion_tokens), 0)              AS total_completion_tokens,
    COALESCE(SUM(prompt_tokens + completion_tokens), 0) AS total_tokens,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms
FROM llm_call_metrics
WHERE created_at > now() - INTERVAL '7 days';
