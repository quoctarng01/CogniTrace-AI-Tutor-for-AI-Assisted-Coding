-- ============================================================
-- V015: review_events log for concept mastery trajectory
-- ============================================================
--
-- Purpose: The existing `review_cards` table holds only the *current* SM-2
-- state per (user, concept). To visualize per-concept mastery *over time*
-- (the contribution #2 trajectory visualization described in
-- docs/THESIS-05-FUTURE-WORK-TIER1.md §2), we need a row per rating event.
--
-- Schema notes:
--   * `rating` mirrors the four-button rating vocabulary used by the
--     frontend (again | hard | good | easy). We store it as text for
--     human-readability — the router already maps this to SM-2 quality.
--   * `quality` is the numeric 0–5 SM-2 quality, kept for analysis
--     scripts that don't want to re-encode.
--   * `concept_tag` is denormalized so the trajectory endpoint can
--     group by it without joining `review_cards` (which is correct
--     but slower on the dashboard widget).
--   * `trace_id` is nullable so we can later backfill events that
--     pre-date this migration (the `submit_review` endpoint only
--     fires for *new* ratings, but the events table will get every
--     rating going forward).
--   * `mastery_after` is a 0..1 score derived from
--     repetitions / (repetitions + 3). This is a cheap, monotone
--     proxy for mastery that does not require a Bayesian Knowledge
--     Tracing model and is sufficient for the visualization. The
--     methodology section of the thesis cites this as a deliberate
--     simplification; see EDGE (Shivam et al., 2025) for the BKT
--     alternative if a stronger model is required.
-- ============================================================

CREATE TABLE IF NOT EXISTS review_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES profiles(id) ON DELETE CASCADE,
    card_id         UUID REFERENCES review_cards(id) ON DELETE CASCADE,
    trace_id        UUID REFERENCES traces(id) ON DELETE SET NULL,
    concept_tag     TEXT NOT NULL,
    rating          TEXT NOT NULL CHECK (rating IN ('again', 'hard', 'good', 'easy')),
    quality         INT  NOT NULL CHECK (quality BETWEEN 0 AND 5),
    -- SM-2 state *before* this rating was applied
    prev_repetitions INT NOT NULL DEFAULT 0,
    prev_interval_days INT NOT NULL DEFAULT 1,
    prev_easiness_factor FLOAT NOT NULL DEFAULT 2.5,
    -- SM-2 state *after* this rating was applied
    new_repetitions INT NOT NULL DEFAULT 0,
    new_interval_days INT NOT NULL DEFAULT 1,
    new_easiness_factor FLOAT NOT NULL DEFAULT 2.5,
    -- 0..1 mastery proxy for the trajectory SVG. monotone in repetitions.
    mastery_after   FLOAT NOT NULL CHECK (mastery_after BETWEEN 0 AND 1),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Most common query: "all events for one user ordered by time, by concept"
CREATE INDEX IF NOT EXISTS idx_review_events_user_time
    ON review_events(user_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_review_events_user_concept
    ON review_events(user_id, concept_tag, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_review_events_card
    ON review_events(card_id, occurred_at DESC);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE review_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own_review_events" ON review_events FOR ALL
    USING (user_id = auth.uid());

-- Backfill helper for existing reviews: synthesize events from the
-- current review_cards state. Runs at most once per card. Only used
-- in the rare case a user has review_cards rows but no events yet
-- (which will be the case for any user who reviewed before this
-- migration shipped). The endpoint exposes this as a one-shot call
-- to avoid duplicating events.
--
-- We deliberately do NOT backfill in the migration itself so the
-- migration is safe to run multiple times.
