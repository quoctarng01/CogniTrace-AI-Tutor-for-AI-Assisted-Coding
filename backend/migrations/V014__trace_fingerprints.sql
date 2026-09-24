-- ============================================================
-- V014: Trace fingerprints (Workstream 12 / thesis Contribution #4)
-- ============================================================
-- A *trace fingerprint* is a deterministic, human-readable signature
-- that summarises the runtime structure of a saved trace. Used by:
--   - /api/traces/{id}/fingerprint (JSON)
--   - /fingerprint/{share_token}/card.svg (OG/Twitter image)
--   - /fingerprint/{share_token} (human-facing share page)
--
-- Why a separate table (not columns on `traces`):
--   - The fingerprint JSON can grow (ast_metrics, exception_types)
--     without bloating the row that the tracer API returns every time.
--   - One trace → at most one fingerprint. Uniqueness is on trace_id.
--     Re-saving a trace should UPDATE the existing fingerprint row
--     rather than insert a duplicate.
--   - The `signature` column (10-char SHA-1 prefix) supports dedupe
--     queries across the corpus without ever exposing the code.
--
-- Why nullable user_id / trace_id:
--   - ON DELETE CASCADE for trace_id: deleting a trace should drop
--     its fingerprint (we never need a fingerprint of a deleted trace).
--   - user_id is denormalised for fast "my fingerprints" queries; we
--     backfill it from traces on insert and trust the application's
--     service-role writes (no FK because profiles/user_id structure
--     varies across migrations).
-- ============================================================

CREATE TABLE IF NOT EXISTS trace_fingerprints (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id             UUID NOT NULL UNIQUE
        REFERENCES traces(id) ON DELETE CASCADE,
    user_id              UUID,                          -- denormalised from traces.user_id
    -- Wire format ---------------------------------------------------------
    -- All values are derived from code + steps; the JSON column is the
    -- canonical wire payload (see Fingerprint.to_dict()).
    fingerprint_json     JSONB NOT NULL,
    compact              TEXT NOT NULL,                 -- ◆-B2-R1-E0-LO2-EX12-CC🟡-T47ms
    short_form           TEXT NOT NULL,                 -- ◆B2·R1·E0·LO2·T47ms
    signature            TEXT NOT NULL,                 -- 10-char SHA-1 prefix for dedupe
    -- Human-readable components (denormalised for cheap scans/queries) ----
    branches             INT NOT NULL DEFAULT 0,
    recursion_depth      INT NOT NULL DEFAULT 0,
    loop_iterations      INT NOT NULL DEFAULT 0,
    total_steps          INT NOT NULL DEFAULT 0,
    conceptual_complexity TEXT NOT NULL DEFAULT '🟢',   -- '🟢' | '🟡' | '🔴'
    total_duration_ms    REAL NOT NULL DEFAULT 0,
    exception_types      TEXT[] NOT NULL DEFAULT '{}',
    -- Audit --------------------------------------------------------------
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Indexes ──────────────────────────────────────────────────────────

-- Fast lookup by trace id (the hot path: GET /api/traces/{id}/fingerprint)
CREATE INDEX IF NOT EXISTS idx_trace_fingerprints_trace_id
    ON trace_fingerprints(trace_id);

-- Dedupe analysis: "how many other traces share this fingerprint?"
CREATE INDEX IF NOT EXISTS idx_trace_fingerprints_signature
    ON trace_fingerprints(signature);

-- "My fingerprints" listing by user, newest first
CREATE INDEX IF NOT EXISTS idx_trace_fingerprints_user_created
    ON trace_fingerprints(user_id, created_at DESC);

-- Thesis rubric rollups: "all RED-complexity traces in the last 30 days"
CREATE INDEX IF NOT EXISTS idx_trace_fingerprints_complexity_created
    ON trace_fingerprints(conceptual_complexity, created_at DESC);

-- ── updated_at trigger ────────────────────────────────────────────────
-- Bumps updated_at on every UPDATE so the OG-card endpoint can detect
-- when the cached SVG was rendered against a stale fingerprint.
CREATE OR REPLACE FUNCTION touch_trace_fingerprint_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_trace_fingerprint_touch_updated_at ON trace_fingerprints;
CREATE TRIGGER trg_trace_fingerprint_touch_updated_at
    BEFORE UPDATE ON trace_fingerprints
    FOR EACH ROW
    EXECUTE FUNCTION touch_trace_fingerprint_updated_at();

-- ── RLS ──────────────────────────────────────────────────────────────
-- Like `traces`: only the owner can read their own fingerprint rows.
-- Writes happen via the service role (bypasses RLS). The fingerprint
-- does NOT need to be public to render an OG card — the share-token
-- endpoint looks up the trace first (via the existing /traces policy)
-- and joins to fingerprint by trace_id inside the service-role call.
ALTER TABLE trace_fingerprints ENABLE ROW LEVEL SECURITY;

-- Owners can read their own fingerprint. Service role bypasses for writes
-- and for the share-page path.
DROP POLICY IF EXISTS "own_trace_fingerprint" ON trace_fingerprints;
CREATE POLICY "own_trace_fingerprint" ON trace_fingerprints
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM traces t
            WHERE t.id = trace_fingerprints.trace_id
              AND t.user_id = auth.uid()
        )
    );

-- ── Backfill is a no-op ──────────────────────────────────────────────
-- Pre-V014 traces have no fingerprint. The application computes one
-- lazily on first access and INSERTs it. No backfill query here.