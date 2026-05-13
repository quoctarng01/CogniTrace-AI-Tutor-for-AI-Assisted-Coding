-- ============================================================
-- CodeScope Database Migrations
-- V001: Initial Schema
-- ============================================================

-- Profiles (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS profiles (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    experience_level TEXT CHECK (experience_level IN ('student', 'junior', 'mid')),
    ai_tools_usage   TEXT CHECK (ai_tools_usage IN ('none', 'light', 'moderate', 'heavy')),
    python_years     INT DEFAULT 0,
    ollama_endpoint  TEXT DEFAULT 'https://ollama.com/api',
    stripe_customer_id TEXT,
    plan             TEXT DEFAULT 'free' CHECK (plan IN ('free', 'pro')),
    created_at       TIMESTAMPTZ DEFAULT now()
);

-- Traces
CREATE TABLE IF NOT EXISTS traces (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES profiles(id) ON DELETE CASCADE,
    code         TEXT NOT NULL,
    language     TEXT DEFAULT 'python',
    steps        JSONB NOT NULL,
    concept_tags TEXT[] DEFAULT '{}',
    is_public    BOOLEAN DEFAULT false,
    share_token  TEXT UNIQUE DEFAULT encode(gen_random_bytes(16), 'hex'),
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- Review Cards (spaced repetition)
CREATE TABLE IF NOT EXISTS review_cards (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID REFERENCES profiles(id) ON DELETE CASCADE,
    trace_id         UUID REFERENCES traces(id) ON DELETE CASCADE,
    concept_tag      TEXT,
    easiness_factor  FLOAT DEFAULT 2.5,
    interval_days    INT DEFAULT 1,
    repetitions      INT DEFAULT 0,
    next_review_date DATE,
    last_reviewed_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT now()
);

-- Explanations (cached LLM responses)
CREATE TABLE IF NOT EXISTS explanations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id          UUID REFERENCES traces(id) ON DELETE CASCADE,
    line_number       INT NOT NULL,
    explanation_text  TEXT NOT NULL,
    cache_key         TEXT NOT NULL,
    model_used        TEXT DEFAULT 'ollama',
    model_name        TEXT,
    cached            BOOLEAN DEFAULT false,
    human_rating      INT CHECK (human_rating BETWEEN 1 AND 5),
    pattern_category  TEXT,
    created_at        TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_traces_user_id ON traces(user_id);
CREATE INDEX IF NOT EXISTS idx_traces_share_token ON traces(share_token);
CREATE INDEX IF NOT EXISTS idx_review_cards_user_id ON review_cards(user_id);
CREATE INDEX IF NOT EXISTS idx_review_cards_next_date ON review_cards(next_review_date);
CREATE INDEX IF NOT EXISTS idx_explanations_cache_key ON explanations(cache_key);
CREATE INDEX IF NOT EXISTS idx_explanations_trace_id ON explanations(trace_id);

-- Composite index for the most common query: "get all due cards for a user"
CREATE INDEX IF NOT EXISTS idx_review_cards_user_next_date
ON review_cards(user_id, next_review_date);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE profiles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE traces        ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_cards  ENABLE ROW LEVEL SECURITY;
ALTER TABLE explanations  ENABLE ROW LEVEL SECURITY;

-- Profiles
CREATE POLICY "own_profile" ON profiles FOR ALL USING (user_id = auth.uid());

-- Traces
CREATE POLICY "own_traces" ON traces FOR ALL USING (user_id = auth.uid());
CREATE POLICY "public_traces" ON traces FOR SELECT USING (is_public = true);

-- Review Cards
CREATE POLICY "own_cards" ON review_cards FOR ALL USING (user_id = auth.uid());

-- Explanations
CREATE POLICY "own_explanations" ON explanations FOR ALL
    USING (trace_id IN (SELECT id FROM traces WHERE user_id = auth.uid()));

-- ============================================================
-- Helper Functions
-- ============================================================

-- Get cached explanation by cache_key
CREATE OR REPLACE FUNCTION get_explanation(p_cache_key TEXT)
RETURNS SETOF explanations AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM explanations
    WHERE cache_key = p_cache_key
    LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
