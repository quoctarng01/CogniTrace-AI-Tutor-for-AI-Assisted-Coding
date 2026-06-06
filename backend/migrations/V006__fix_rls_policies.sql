-- ============================================================
-- CodeScope Database Migrations
-- V006: Fix RLS Policies
-- ============================================================

-- Drop old policies that incorrectly compared profiles.id to auth.uid()
DROP POLICY IF EXISTS "own_traces" ON traces;
DROP POLICY IF EXISTS "own_cards" ON review_cards;
DROP POLICY IF EXISTS "own_explanations" ON explanations;

-- Recreate policies with correct user profile mapping via profiles.user_id = auth.uid()

-- Traces
CREATE POLICY "own_traces" ON traces FOR ALL
    USING (user_id IN (SELECT id FROM profiles WHERE user_id = auth.uid()));

-- Review Cards
CREATE POLICY "own_cards" ON review_cards FOR ALL
    USING (user_id IN (SELECT id FROM profiles WHERE user_id = auth.uid()));

-- Explanations
CREATE POLICY "own_explanations" ON explanations FOR ALL
    USING (trace_id IN (SELECT id FROM traces WHERE user_id IN (SELECT id FROM profiles WHERE user_id = auth.uid())));
