-- ============================================================
-- CodeScope Database Migrations
-- V007: Optimize RLS Policies using EXISTS
-- ============================================================

-- Drop old subquery policies
DROP POLICY IF EXISTS "own_traces" ON traces;
DROP POLICY IF EXISTS "own_cards" ON review_cards;
DROP POLICY IF EXISTS "own_explanations" ON explanations;

-- Recreate policies using high-performance EXISTS

-- Traces: Check if there exists a profile row matching the trace user_id and authenticated user_id
CREATE POLICY "own_traces" ON traces FOR ALL
    USING (EXISTS (
        SELECT 1 FROM profiles 
        WHERE profiles.id = traces.user_id 
          AND profiles.user_id = auth.uid()
    ));

-- Review Cards: Check if there exists a profile row matching the review card user_id and authenticated user_id
CREATE POLICY "own_cards" ON review_cards FOR ALL
    USING (EXISTS (
        SELECT 1 FROM profiles 
        WHERE profiles.id = review_cards.user_id 
          AND profiles.user_id = auth.uid()
    ));

-- Explanations: Check if there exists a trace owned by a profile matching the authenticated user
CREATE POLICY "own_explanations" ON explanations FOR ALL
    USING (EXISTS (
        SELECT 1 FROM traces 
        JOIN profiles ON profiles.id = traces.user_id
        WHERE traces.id = explanations.trace_id 
          AND profiles.user_id = auth.uid()
    ));
