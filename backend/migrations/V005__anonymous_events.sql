-- Anonymous event tracking for churn analysis

CREATE TABLE IF NOT EXISTS anonymous_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  anon_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  metadata JSONB,
  occurred_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE anonymous_events ENABLE ROW LEVEL SECURITY;

-- Policy: anyone can INSERT (fire-and-forget)
CREATE POLICY "public_insert" ON anonymous_events FOR INSERT TO anon WITH CHECK (true);

-- Policy: authenticated users can SELECT
CREATE POLICY "authenticated_read" ON anonymous_events FOR SELECT TO authenticated USING (true);
