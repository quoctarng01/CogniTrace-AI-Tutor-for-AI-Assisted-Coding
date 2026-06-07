/**
 * Supabase client — auth and database.
 */
import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? '';
const MANUAL_SESSION_KEY = 'cognitrace-manual-session';

let supabase: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!supabase && supabaseUrl && supabaseAnonKey) {
    supabase = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        storageKey: 'supabase-cognitrace-auth',
      },
    });
  }
  if (!supabase) {
    throw new Error(
      'Supabase not initialized. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.'
    );
  }
  return supabase;
}

export async function getAuthToken(): Promise<string | null> {
  try {
    // First try the normal Supabase session
    const { data } = await getSupabase().auth.getSession();
    if (data?.session?.access_token) {
      return data.session.access_token;
    }

    // Fallback to manual storage for SSR compatibility
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(MANUAL_SESSION_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed?.session?.access_token) {
          await getSupabase().auth.setSession(parsed.session);
          return parsed.session.access_token;
        }
      }
    }
    return null;
  } catch {
    return null;
  }
}

export async function signUp(email: string, password: string) {
  try {
    const { data, error } = await getSupabase().auth.signUp({ email, password });
    if (error) throw error;
    return data;
  } catch (err) {
    if (err instanceof TypeError && err.message === 'Failed to fetch') {
      throw new Error(
        'Cannot reach Supabase. Check your internet connection and that the Supabase project URL is correct.'
      );
    }
    throw err;
  }
}

export async function signIn(email: string, password: string) {
  const { data, error } = await getSupabase().auth.signInWithPassword({ email, password });
  if (error) {
    throw error;
  }

  // Manually ensure session is persisted (workaround for Next.js SSR issues)
  if (data.session) {
    // 1. Update Supabase's internal state
    await getSupabase().auth.setSession({
      access_token: data.session.access_token,
      refresh_token: data.session.refresh_token,
    });

    // 2. Also save to manual storage for fallback
    const storageData = {
      session: data.session,
      expiresAt: Date.now() + (data.session.expires_in ?? 3600) * 1000,
    };
    if (typeof window !== 'undefined') {
      localStorage.setItem(MANUAL_SESSION_KEY, JSON.stringify(storageData));
    }
  }

  return data;
}

export async function signOut() {
  const { error } = await getSupabase().auth.signOut();
  if (error) throw error;
}
