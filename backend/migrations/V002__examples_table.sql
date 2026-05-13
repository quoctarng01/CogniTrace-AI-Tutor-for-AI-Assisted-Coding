-- File: backend/migrations/V002__examples_table.sql
-- Run ONCE against your Supabase database before Step 2.

BEGIN;

-- ── Create examples table ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS examples (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category              TEXT NOT NULL,
    title                TEXT NOT NULL,
    code                 TEXT NOT NULL,
    why_ai_generates_this TEXT NOT NULL,
    annotations          JSONB NOT NULL DEFAULT '[]',
    explanation          TEXT NOT NULL,
    common_mistakes      TEXT[] NOT NULL DEFAULT '{}',
    review_interval      TEXT NOT NULL DEFAULT '1,3,7,14',
    created_at           TIMESTAMPTZ DEFAULT now(),
    updated_at           TIMESTAMPTZ DEFAULT now()
);

-- ── Index for category filter ──────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_examples_category ON examples(category);

-- ── Auto-update updated_at trigger ─────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER examples_updated_at
    BEFORE UPDATE ON examples
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ── Row Level Security ─────────────────────────────────────────
ALTER TABLE examples ENABLE ROW LEVEL SECURITY;

-- Anyone can SELECT (browse is public)
CREATE POLICY "public_read_examples" ON examples
    FOR SELECT USING (true);

-- No inserts/updates/deletes from client apps
CREATE POLICY "no_insert_examples" ON examples FOR INSERT WITH CHECK (false);
CREATE POLICY "no_update_examples" ON examples FOR UPDATE USING (false);
CREATE POLICY "no_delete_examples" ON examples FOR DELETE USING (false);

-- ── Insert the 25 example records ────────────────────────────
-- (Next step will have the full INSERT statement.
--  Run the INSERT after Step 1 is verified.)

COMMIT;
