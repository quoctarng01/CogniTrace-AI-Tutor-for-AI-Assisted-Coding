// frontend/app/dashboard/mastery/page.tsx
'use client';
/**
 * Mastery trajectory page (THESIS-05 §2) — animated SVG per-concept
 * mastery over time. Sits under the dashboard top-bar so users can
 * drill into long-term concept health beyond the streak / due-cards
 * view on the main dashboard.
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { getSupabase, getAuthToken } from '@/lib/supabase';
import { fetchMasteryTrajectory } from '@/lib/api';
import type { MasteryTrajectory as MasteryTrajectoryData } from '@/types/trajectory';
import { MasteryTrajectory } from '@/components/tracer/MasteryTrajectory';
import styles from './page.module.css';

const WINDOW_OPTIONS: Array<{ label: string; days: number }> = [
  { label: '7 days', days: 7 },
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
];

export default function MasteryPage() {
  const router = useRouter();
  const [windowDays, setWindowDays] = useState<number>(30);
  const [trajectory, setTrajectory] = useState<MasteryTrajectoryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      await getAuthToken();
      const { data } = await getSupabase().auth.getSession();
      if (!data?.session) {
        router.replace('/auth/login');
        return;
      }
      setUserEmail(data.session.user.email ?? null);

      try {
        setLoading(true);
        const t = await fetchMasteryTrajectory(windowDays);
        setTrajectory(t);
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.message === 'AUTH_REQUIRED') {
          router.replace('/auth/login');
          return;
        }
        setError(
          err instanceof Error ? err.message : 'Failed to load mastery data',
        );
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router, windowDays]);

  const handleSignOut = useCallback(async () => {
    const { signOut } = await import('@/lib/supabase');
    await signOut();
    router.replace('/auth/login');
  }, [router]);

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Link href="/dashboard" className={styles.brandLink}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </Link>
        <div className={styles.actions}>
          <Link href="/tracer" className={styles.newTraceBtn}>
            + New Trace
          </Link>
          <Link href="/dashboard" className={styles.navDashboardLink}>
            Dashboard
          </Link>
          <div className={styles.userMenu}>
            <span className={styles.userEmail}>{userEmail}</span>
            <button onClick={handleSignOut} className={styles.signOutBtn}>
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className={styles.main}>
        <section className={styles.header}>
          <h1 className={styles.title}>Mastery trajectory</h1>
          <p className={styles.subtitle}>
            How your concept-level understanding evolves over time. Each line is a
            concept you have reviewed; the dot at the right is your current mastery.
          </p>
        </section>

        <div className={styles.controls} role="group" aria-label="Time window">
          {WINDOW_OPTIONS.map(opt => (
            <button
              key={opt.days}
              type="button"
              className={
                opt.days === windowDays
                  ? `${styles.windowBtn} ${styles.windowBtnActive}`
                  : styles.windowBtn
              }
              aria-pressed={opt.days === windowDays}
              onClick={() => setWindowDays(opt.days)}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {error && (
          <div className={styles.errorBanner}>
            <span>⚠</span> {error}
          </div>
        )}

        <section className={styles.chartCard} aria-busy={loading}>
          {loading ? (
            <div className={styles.loading}>
              <span className={styles.spinner}>◈</span> Loading trajectory…
            </div>
          ) : trajectory ? (
            <MasteryTrajectory trajectory={trajectory} windowDays={windowDays} />
          ) : null}
        </section>

        <section className={styles.footnote}>
          <p>
            Mastery is a 0–100% proxy derived from SM-2 repetitions (more
            successful recalls → higher mastery). A pulsing dot means a recent
            <em> hard</em> or <em>again</em> rating — a concept to revisit.
          </p>
        </section>
      </main>
    </div>
  );
}
