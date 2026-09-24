-- ============================================================
-- V013: Study sessions for empirical RQ1 (W1 of pilot plan)
-- ============================================================
-- A `study_session` is one continuous interaction by a pilot
-- participant, identified by an opaque client-generated UUID.
-- Sessions are opt-in: when a client sends `X-Study-Session: <uuid>`
-- on an LLM or trace request, every downstream row that the backend
-- writes (LLM call metrics, explanations) is tagged with that UUID.
--
-- When the header is absent (production traffic, not the pilot),
-- every column/foreign-key below is NULL. The instrumentation is
-- zero-cost for non-pilot traffic.
--
-- The `study_id` (e.g. 'P001') is the *anonymized* participant
-- identifier — separate from `user_id`. Per THESIS-01 protocol,
-- participants cannot be re-identified from `study_id` alone.
-- `study_id` is recorded by the front-end only when the participant
-- is enrolled; for unauthenticated pilots, the frontend generates
-- a stable `study_id` on first mount and persists it to localStorage.

CREATE TABLE IF NOT EXISTS study_sessions (
    id                  UUID PRIMARY KEY,             -- the client-generated UUID from X-Study-Session
    study_id            TEXT,                         -- anonymized participant code ('P001', 'P002', ...)
    condition           TEXT,                         -- 'A' | 'B' | 'C' | 'C_prime' (within-subjects arm)
    task_id             TEXT,                         -- identifier of the debugging task being attempted
    user_agent          TEXT,                         -- captured server-side for reproducibility
    client_started_at   TIMESTAMPTZ,                  -- first time the frontend saw this session_id
    server_started_at   TIMESTAMPTZ DEFAULT now(),   -- first request received with this id
    server_last_seen_at TIMESTAMPTZ DEFAULT now(),   -- last request received (updated by trigger)
    ended_at            TIMESTAMPTZ,                  -- explicit close from the client
    metadata            JSONB DEFAULT '{}'            -- free-form (e.g. condition order, counterbalance key)
);

-- Column-level comments document the schema for thesis readers.
COMMENT ON COLUMN study_sessions.study_id IS
    'Anonymized participant code. Generated client-side on first visit, persisted to localStorage.';
COMMENT ON COLUMN study_sessions.condition IS
    'Within-subjects arm for this session: A (Python Tutor), B (PT + ungrounded LLM), C (CogniTrace) or C_prime (C without checkpoints).';
COMMENT ON COLUMN study_sessions.task_id IS
    'Identifier of the debugging task the participant is currently attempting.';

CREATE INDEX IF NOT EXISTS idx_study_sessions_study_id
    ON study_sessions(study_id);

CREATE INDEX IF NOT EXISTS idx_study_sessions_server_started_at
    ON study_sessions(server_started_at);

-- Update `server_last_seen_at` on any UPDATE so we can compute session duration
-- (server_last_seen_at - server_started_at) without an additional timestamp.
CREATE OR REPLACE FUNCTION study_session_touch_last_seen()
RETURNS TRIGGER AS $$
BEGIN
    NEW.server_last_seen_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_study_session_touch_last_seen ON study_sessions;
CREATE TRIGGER trg_study_session_touch_last_seen
    BEFORE UPDATE ON study_sessions
    FOR EACH ROW
    EXECUTE FUNCTION study_session_touch_last_seen();

-- ============================================================
-- Wire study_session into llm_call_metrics
-- ============================================================
-- Nullable FK. Backfilling existing rows would require a study
-- session, which we don't have for production traffic, so we add
-- the column nullable with no default.
ALTER TABLE llm_call_metrics
    ADD COLUMN IF NOT EXISTS study_session_id UUID
        REFERENCES study_sessions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_llm_call_metrics_study_session
    ON llm_call_metrics(study_session_id);

-- Same for explanations (one explanation row per cache hit).
ALTER TABLE explanations
    ADD COLUMN IF NOT EXISTS study_session_id UUID
        REFERENCES study_sessions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_explanations_study_session
    ON explanations(study_session_id);

-- ============================================================
-- RLS
-- ============================================================
ALTER TABLE study_sessions ENABLE ROW LEVEL SECURITY;

-- Pilot participants (authenticated) can read their own sessions (matched by study_id);
-- the service role (used by the backend) bypasses RLS to insert/update rows.
CREATE POLICY "own_study_session" ON study_sessions
    FOR SELECT USING (
        study_id = current_setting('app.pilot_study_id', true)
    );

-- Inserts/updates are server-side via service-role key. End-users can't write directly.
-- No explicit INSERT/UPDATE policy is needed: with RLS enabled and no matching policy,
-- direct inserts from anon/authenticated clients are denied. Service-role bypasses it.
