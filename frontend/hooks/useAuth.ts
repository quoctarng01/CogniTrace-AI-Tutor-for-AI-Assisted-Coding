/**
 * useAuth — provides authentication state across all pages.
 *
 * Replaces the repeated getSupabase().auth.getSession() pattern in each page.
 * Returns isAuthenticated, token, session, and isLoading.
 *
 * Uses onAuthStateChange so the state stays fresh when:
 *   - The session expires (SIGNED_OUT event)
 *   - The user signs in from another tab (SIGNED_IN event)
 *   - The token is silently refreshed (TOKEN_REFRESHED event)
 */
import { useState, useEffect } from 'react';
import { getSupabase } from '@/lib/supabase';
import type { Session } from '@supabase/supabase-js';

export interface UseAuthReturn {
  isAuthenticated: boolean;
  token: string | null;
  session: Session | null;
  isLoading: boolean;
}

export function useAuth(): UseAuthReturn {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const supabase = getSupabase();

    // 1. Get the initial session synchronously so the first render is correct.
    supabase.auth.getSession().then(({ data }) => {
      const s = data?.session ?? null;
      setSession(s);
      setToken(s?.access_token ?? null);
      setIsAuthenticated(!!s);
      setIsLoading(false);
    });

    // 2. Subscribe to all future auth state changes.
    //    This fires on: SIGNED_IN, SIGNED_OUT, TOKEN_REFRESHED, USER_UPDATED, etc.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setToken(newSession?.access_token ?? null);
      setIsAuthenticated(!!newSession);
      setIsLoading(false);
    });

    // 3. Cleanup: unsubscribe when the component using this hook unmounts.
    return () => {
      subscription.unsubscribe();
    };
  }, []); // Empty deps: runs once on mount, subscription handles updates.

  return { isAuthenticated, token, session, isLoading };
}
