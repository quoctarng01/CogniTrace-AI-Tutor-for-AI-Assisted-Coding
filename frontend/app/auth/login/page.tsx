// frontend/app/auth/login/page.tsx
'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { signIn, getSupabase } from '@/lib/supabase';
import styles from '../auth.module.css';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getSupabase()
      .auth.getSession()
      .then(({ data }) => {
        if (data?.session) router.replace('/dashboard');
      });
  }, [router]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setLoading(true);
      try {
        await signIn(email, password);
        // Verify localStorage is accessible before navigating
        await new Promise(resolve => setTimeout(resolve, 200));
        const stored = localStorage.getItem('codescope-manual-session');
        console.log(
          '[DEBUG] Login - verifying localStorage before nav:',
          stored ? 'EXISTS' : 'NULL'
        );
        if (!stored) {
          // Try one more time after a delay
          await new Promise(resolve => setTimeout(resolve, 500));
        }
        router.replace('/dashboard');
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Login failed';
        if (msg.includes('Invalid login credentials')) {
          setError('Invalid email or password. Please try again.');
        } else if (msg.includes('Email not confirmed')) {
          setError('Email not confirmed. Check your inbox for a confirmation email.');
        } else {
          setError(msg);
        }
      } finally {
        setLoading(false);
      }
    },
    [email, password, router]
  );

  const handleGithubSignIn = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const { error } = await getSupabase().auth.signInWithOAuth({
        provider: 'github',
        options: {
          redirectTo: window.location.origin + '/auth/callback',
        },
      });
      if (error) throw error;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'GitHub sign in failed');
      setLoading(false);
    }
  }, []);

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </div>
        <h1 className={styles.title}>Sign in to your account</h1>
        <p className={styles.subtitle}>
          New here?{' '}
          <Link href="/auth/signup" className={styles.link}>
            Create an account
          </Link>
        </p>
        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label htmlFor="email" className={styles.label}>
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="email"
              className={styles.input}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="password" className={styles.label}>
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Your password"
              required
              autoComplete="current-password"
              className={styles.input}
            />
          </div>
          {error && (
            <div className={styles.error}>
              <span>⚠</span> {error}
            </div>
          )}
          <button
            type="submit"
            disabled={loading || !email || !password}
            className={styles.submitBtn}
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className={styles.divider}>or</div>

        <button
          type="button"
          disabled={loading}
          onClick={handleGithubSignIn}
          className={styles.githubBtn}
        >
          <svg
            viewBox="0 0 24 24"
            fill="currentColor"
            style={{ width: '20px', height: '20px' }}
          >
            <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.579.688.481C19.137 20.162 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
          </svg>
          Sign in with GitHub
        </button>

        <p className={styles.footer}>
          <Link href="/" className={styles.link}>
            ← Back to tracer
          </Link>
        </p>
      </div>
    </div>
  );
}
