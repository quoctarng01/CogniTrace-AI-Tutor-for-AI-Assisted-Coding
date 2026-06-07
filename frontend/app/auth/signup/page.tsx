// frontend/app/auth/signup/page.tsx
'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { signUp, getSupabase } from '@/lib/supabase';
import styles from '../auth.module.css';

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

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
      if (password.length < 6) {
        setError('Password must be at least 6 characters.');
        return;
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match.');
        return;
      }
      setLoading(true);
      try {
        const data = await signUp(email, password);
        if (data.user && !data.session) {
          setSuccessMessage(
            'Account created! Check your email to confirm your account before signing in.'
          );
        } else {
          router.push('/dashboard');
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Sign up failed';
        if (msg.includes('already registered')) {
          setError('An account with this email already exists.');
        } else {
          setError(msg);
        }
      } finally {
        setLoading(false);
      }
    },
    [email, password, confirmPassword, router]
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
      setError(err instanceof Error ? err.message : 'GitHub sign up failed');
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
        <h1 className={styles.title}>Create your account</h1>
        <p className={styles.subtitle}>
          Already have an account?{' '}
          <Link href="/auth/login" className={styles.link}>
            Sign in
          </Link>
        </p>
        {successMessage ? (
          <div className={styles.success}>
            <span>✓</span> {successMessage}
            <p className={styles.successBack}>
              <Link href="/auth/login" className={styles.link}>
                ← Back to sign in
              </Link>
            </p>
          </div>
        ) : (
          <>
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
                  placeholder="At least 6 characters"
                  required
                  minLength={6}
                  autoComplete="new-password"
                  className={styles.input}
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="confirmPassword" className={styles.label}>
                  Confirm password
                </label>
                <input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  placeholder="Repeat your password"
                  required
                  autoComplete="new-password"
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
                disabled={loading || !email || !password || !confirmPassword}
                className={styles.submitBtn}
              >
                {loading ? 'Creating account...' : 'Create account'}
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
              Sign up with GitHub
            </button>
          </>
        )}
        <p className={styles.footer}>
          <Link href="/" className={styles.link}>
            ← Back to tracer
          </Link>
        </p>
      </div>
    </div>
  );
}
