// frontend/app/supabase-provider.tsx
'use client';
/**
 * Purpose: Client-side Supabase context. Every page reads `useSupabase()` to get the auth client.
 * Collaborators: —
 * Last significant change: Workstream 9
 */


import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { getSupabase } from '@/lib/supabase';

export function SupabaseListener() {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const supabase = getSupabase();
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(event => {
      // Refresh the current route on any auth event — keeps UI in sync across tabs
      if (event === 'SIGNED_IN' || event === 'SIGNED_OUT' || event === 'TOKEN_REFRESHED') {
        router.refresh();
      }
    });
    return () => subscription.unsubscribe();
  }, [router, pathname]);

  return null;
}
