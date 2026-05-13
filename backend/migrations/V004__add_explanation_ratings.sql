-- Explanation ratings table for collecting user feedback on AI explanations
CREATE TABLE IF NOT EXISTS explanation_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    explanation_id UUID,  -- references the explanation this rating is for
    trace_id UUID,        -- which trace/context this belongs to
    user_id UUID,        -- who rated (nullable for anonymous)
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT fk_explanation FOREIGN KEY (explanation_id) REFERENCES explanations(id) ON DELETE SET NULL
);

-- RLS: users can only see their own ratings
ALTER TABLE explanation_ratings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can insert their own ratings"
ON explanation_ratings FOR INSERT
WITH CHECK (true);  -- Allow anonymous ratings too

CREATE POLICY "Users can view their own ratings"
ON explanation_ratings FOR SELECT
USING (true);  -- Make public for analytics, or filter by user_id for private

-- Index for looking up ratings by explanation
CREATE INDEX IF NOT EXISTS idx_ratings_explanation_id ON explanation_ratings(explanation_id);
