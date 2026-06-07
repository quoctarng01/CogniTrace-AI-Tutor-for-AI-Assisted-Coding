// frontend/app/auth/callback/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getSupabase } from '@/lib/supabase';

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const supabase = getSupabase();

    // Check if there is a session
    supabase.auth.getSession().then(async ({ data: { session }, error }) => {
      if (error) {
        setError(error.message);
        return;
      }

      if (session) {
        // Persist session manually for SSR compatibility (matching signIn in supabase.ts)
        const storageData = {
          session,
          expiresAt: Date.now() + (session.expires_in ?? 3600) * 1000,
        };
        localStorage.setItem('codescope-manual-session', JSON.stringify(storageData));

        // Redirect to dashboard
        router.replace('/dashboard');
      } else {
        // If no session is found immediately, listen to auth state changes (handles redirects)
        const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, newSession) => {
          if (event === 'SIGNED_IN' && newSession) {
            const storageData = {
              session: newSession,
              expiresAt: Date.now() + (newSession.expires_in ?? 3600) * 1000,
            };
            localStorage.setItem('codescope-manual-session', JSON.stringify(storageData));
            subscription.unsubscribe();
            router.replace('/dashboard');
          }
        });

        // Timeout fallback if no sign-in event fires in 6 seconds
        const timer = setTimeout(() => {
          subscription.unsubscribe();
          setError('Authentication timeout or failed.');
        }, 6000);

        return () => {
          clearTimeout(timer);
          subscription.unsubscribe();
        };
      }
    });
  }, [router]);

  if (error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0d1117', color: '#f85149', fontFamily: 'sans-serif' }}>
        <div style={{ textAlign: 'center', padding: '20px', background: '#161b22', border: '1px solid #21262d', borderRadius: '8px' }}>
          <h3 style={{ margin: '0 0 10px' }}>Authentication Error</h3>
          <p style={{ color: '#8b949e', margin: '0 0 20px' }}>{error}</p>
          <a href="/auth/login" style={{ color: '#58a6ff', textDecoration: 'none', fontWeight: '500' }}>Back to login</a>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0d1117', color: '#e6edf3', fontFamily: 'sans-serif' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '24px', marginBottom: '12px' }}>◈</div>
        <div>Completing sign in...</div>
      </div>
    </div>
  );
}
