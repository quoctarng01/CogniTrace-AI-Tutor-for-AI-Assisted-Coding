-- ============================================================
-- V012: Explanations grounding-check columns (Workstream 4)
-- ============================================================
-- Adds two columns to the `explanations` table used by the RQ1 manual
-- hallucination-count protocol. The researcher (you) populates these on a
-- sample of N=50 explanations during data analysis.
--
-- The `grounded` column is a binary flag: did the explanation faithfully
-- describe the actual runtime state?
-- The `hallucination_flag` column is free-form text: if grounded=false,
-- what specifically was hallucinated? e.g. "stated x was 5, x was actually 3"
--
-- The application does NOT write to these columns. They are reserved for
-- the manual evaluator during RQ1 analysis.
-- ============================================================

ALTER TABLE explanations
    ADD COLUMN IF NOT EXISTS grounded BOOLEAN;

ALTER TABLE explanations
    ADD COLUMN IF NOT EXISTS hallucination_flag TEXT;

-- A small CHECK so reviewers can mark the "review status":
--   'pending'  — not yet reviewed
--   'reviewed' — manually labeled
--   'disputed' — flagged for second-pass review
ALTER TABLE explanations
    ADD COLUMN IF NOT EXISTS review_status TEXT
        DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'reviewed', 'disputed'));

ALTER TABLE explanations
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

ALTER TABLE explanations
    ADD COLUMN IF NOT EXISTS reviewer_id UUID REFERENCES profiles(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_explanations_review_status
    ON explanations(review_status)
    WHERE review_status != 'pending';

CREATE INDEX IF NOT EXISTS idx_explanations_grounded
    ON explanations(grounded)
    WHERE grounded IS NOT NULL;

-- ============================================================
-- View for the RQ1 analysis report
-- ============================================================
-- Returns one row per reviewed explanation with the trace/code context
-- the reviewer needs to verify grounding. The thesis-defense report
-- references this view.

CREATE OR REPLACE VIEW v_explanations_review_queue AS
SELECT
    e.id,
    e.cache_key,
    e.line_number,
    e.explanation_text,
    e.model_used,
    e.model_name,
    e.grounded,
    e.hallucination_flag,
    e.review_status,
    e.reviewed_at,
    t.id   AS trace_id,
    t.code AS trace_code,
    t.concept_tags,
    t.created_at AS trace_created_at
FROM explanations e
JOIN traces t ON t.id = e.trace_id
WHERE e.review_status != 'pending'
ORDER BY e.reviewed_at DESC;

-- ============================================================
-- Row Level Security
-- ============================================================
-- These columns are written by the researcher during analysis, not by users.
-- No new policies needed: the existing "own_explanations" policy in V001 covers
-- SELECT, and writes go through the service role which bypasses RLS.

-- Allow reviewers (admin profile) to mark an explanation as reviewed.
CREATE POLICY "reviewer_update_explanations" ON explanations
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid() AND p.plan = 'admin'
        )
    );
