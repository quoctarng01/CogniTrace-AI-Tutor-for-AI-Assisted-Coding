-- ============================================================
-- V016: fix review_events RLS to use profile-id semantics
-- ============================================================
--
-- The V015 migration created review_events with
--   user_id UUID REFERENCES profiles(id)
-- but the RLS policy was written as
--   USING (user_id = auth.uid())
-- where auth.uid() returns auth.users.id, NOT profiles.id.
-- In CogniTrace, profiles.id != auth.users.id (a profile is its
-- own row), so the policy silently hides every row from the owning
-- user. Only the service-role path (which bypasses RLS) could see
-- the data, which broke the per-user /api/review/trajectory route.
--
-- This migration drops the broken policy and replaces it with one
-- that resolves "the profile belonging to the calling user" via a
-- subquery. Safe to run multiple times.
-- ============================================================

ALTER TABLE public.review_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "own_review_events" ON public.review_events;

CREATE POLICY "own_review_events" ON public.review_events
    FOR ALL
    USING (
        user_id IN (
            SELECT id FROM public.profiles WHERE user_id = auth.uid()
        )
    )
    WITH CHECK (
        user_id IN (
            SELECT id FROM public.profiles WHERE user_id = auth.uid()
        )
    );
