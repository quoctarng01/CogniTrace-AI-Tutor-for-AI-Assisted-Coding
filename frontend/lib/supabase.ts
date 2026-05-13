/**
 * Supabase client — auth and database.
 */
import { createClient, SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

let supabase: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!supabase && supabaseUrl && supabaseAnonKey) {
    supabase = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        storageKey: "supabase-codescope-auth",
      },
    });
  }
  if (!supabase) {
    throw new Error(
      "Supabase not initialized. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY."
    );
  }
  return supabase;
}

export async function getAuthToken(): Promise<string | null> {
  try {
    console.log("[DEBUG] getAuthToken called");
    
    // First try the normal Supabase session
    const { data } = await getSupabase().auth.getSession();
    console.log("[DEBUG] getAuthToken - Supabase session:", data?.session ? "EXISTS" : "NULL");
    if (data?.session?.access_token) {
      console.log("[DEBUG] getAuthToken - using Supabase session token");
      return data.session.access_token;
    }
    
    // Fallback to our manual storage
    if (typeof window !== "undefined") {
    console.log("[DEBUG] getAuthToken - checking manual storage");
    const key = "codescope-manual-session";
    const stored = localStorage.getItem(key);
    console.log("[DEBUG] getAuthToken - stored value:", stored ? "EXISTS (len=" + stored.length + ")" : "NULL");
    if (stored) {
        const parsed = JSON.parse(stored);
        console.log("[DEBUG] getAuthToken - parsed session:", parsed?.session ? "EXISTS" : "NULL");
        if (parsed?.session?.access_token) {
          console.log("[DEBUG] getAuthToken - restoring session from storage");
          await getSupabase().auth.setSession(parsed.session);
          return parsed.session.access_token;
        }
      }
    }
    console.log("[DEBUG] getAuthToken - returning NULL");
    return null;
  } catch (err) {
    console.error("[DEBUG] getAuthToken error:", err);
    return null;
  }
}

export async function signUp(email: string, password: string) {
  try {
    const { data, error } = await getSupabase().auth.signUp({ email, password });
    if (error) throw error;
    return data;
  } catch (err) {
    if (err instanceof TypeError && err.message === "Failed to fetch") {
      throw new Error(
        "Cannot reach Supabase. Check your internet connection and that the Supabase project URL is correct."
      );
    }
    throw err;
  }
}

export async function signIn(email: string, password: string) {
  const { data, error } = await getSupabase().auth.signInWithPassword({ email, password });
  console.log("[DEBUG] signIn result - data:", data ? "EXISTS" : "NULL");
  console.log("[DEBUG] signIn result - session:", data?.session ? "EXISTS" : "NULL");
  console.log("[DEBUG] signIn result - access_token:", data?.session?.access_token ? "EXISTS" : "NULL");
  if (error) {
    console.log("[DEBUG] signIn error:", error.message);
    throw error;
  }
  
  // Manually ensure session is persisted (workaround for Next.js SSR issues)
  if (data.session) {
    // 1. Update Supabase's internal state
    await getSupabase().auth.setSession({
      access_token: data.session.access_token,
      refresh_token: data.session.refresh_token,
    });
    console.log("[DEBUG] signIn - setSession called");
    
    // 2. Also save to manual storage for fallback
    const storageKey = "codescope-manual-session";
    const storageData = {
      session: data.session,
      expiresAt: Date.now() + (data.session.expires_in ?? 3600) * 1000,
    };
    if (typeof window !== "undefined") {
      console.log("[DEBUG] signIn - saving session to localStorage");
      localStorage.setItem(storageKey, JSON.stringify(storageData));
      console.log("[DEBUG] signIn - localStorage set, key:", storageKey);
      // Verify it was set
      const verify = localStorage.getItem(storageKey);
      console.log("[DEBUG] signIn - verify localStorage:", verify ? "OK" : "FAILED");
    }
  } else {
    console.log("[DEBUG] signIn - NO SESSION in data!");
  }
  
  return data;
}

export async function signOut() {
  const { error } = await getSupabase().auth.signOut();
  if (error) throw error;
}
