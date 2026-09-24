-- ============================================================
-- V013: A/B ablation telemetry (Workstream 11: thesis-defense wow demo)
-- ============================================================
-- Adds two columns to llm_call_metrics so the new /api/llm/ab endpoint
-- can tag which side of the A/B each call was on, and so the judge
-- verdict can be stored alongside the model output.
--
-- Why nullable, not a new column with NOT NULL:
--   - The existing rows (millions of pre-V013 traces) stay valid.
--   - `ablation_mode = NULL` means "normal production call" (no
--     semantic shift for existing queries).
--   - The new endpoint only writes non-null values.
--
-- Why no new table:
--   - These rows are still llm calls. We want them counted in the
--     existing 7-day cache-hit-rate / cost rollups. Adding columns
--     keeps every existing aggregate intact.
-- ============================================================

ALTER TABLE llm_call_metrics
    ADD COLUMN IF NOT EXISTS ablation_mode TEXT,
    ADD COLUMN IF NOT EXISTS judge_score  SMALLINT;

-- Soft check constraint: ablation_mode is one of three known strings.
-- NULL is allowed (the default for pre-existing rows).
ALTER TABLE llm_call_metrics
    DROP CONSTRAINT IF EXISTS llm_call_metrics_ablation_mode_check;
ALTER TABLE llm_call_metrics
    ADD CONSTRAINT llm_call_metrics_ablation_mode_check
    CHECK (ablation_mode IS NULL OR ablation_mode IN ('grounded', 'blind', 'judge'));

-- Index for the demo's "show me only A/B calls" filter, and for the
-- future "ablation_mode × cache_hit_rate" thesis-style analysis.
CREATE INDEX IF NOT EXISTS idx_llm_call_metrics_ablation_created
    ON llm_call_metrics(ablation_mode, created_at)
    WHERE ablation_mode IS NOT NULL;
