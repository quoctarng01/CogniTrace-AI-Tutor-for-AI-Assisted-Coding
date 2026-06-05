// frontend/app/dashboard/page.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { getSupabase, getAuthToken } from '@/lib/supabase';
import { fetchDashboard } from '@/lib/api';
import { formatNextReview } from '@/lib/sm2';
import type { SavedTrace, ReviewCard } from '@/types/user';
import styles from './page.module.css';

function truncateCode(code: string, maxLines = 4): string {
  return code
    .split('\n')
    .filter(l => l.trim())
    .slice(0, maxLines)
    .join('\n');
}

function timeAgo(dateStr: string): string {
  const diffDays = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000);
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return `${Math.floor(diffDays / 30)}mo ago`;
}

export default function DashboardPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [traces, setTraces] = useState<SavedTrace[]>([]);
  const [dueCards, setDueCards] = useState<ReviewCard[]>([]);
  const [streak, setStreak] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      // First try to restore session from localStorage
      await getAuthToken();

      const { data } = await getSupabase().auth.getSession();
      if (!data?.session) {
        router.replace('/auth/login');
        return;
      }
      setUserEmail(data.session.user.email ?? null);

      try {
        const data = await fetchDashboard();
        setTraces(data.traces ?? []);
        setDueCards(data.due_cards ?? []);
        setStreak(data.streak ?? 0);
      } catch (err) {
        if (err instanceof Error && err.message === 'AUTH_REQUIRED') {
          router.replace('/auth/login');
          return;
        }
        setError(err instanceof Error ? err.message : 'Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  const handleSignOut = useCallback(async () => {
    const { signOut } = await import('@/lib/supabase');
    await signOut();
    router.replace('/auth/login');
  }, [router]);

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.loading}>
          <span className={styles.spinner}>◈</span> Loading dashboard...
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Link href="/" className={styles.brandLink}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </Link>
        <div className={styles.actions}>
          <Link href="/tracer" className={styles.newTraceBtn}>
            + New Trace
          </Link>
          <Link href="/examples" className={styles.navExamplesLink}>
            Examples
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
        {error && (
          <div className={styles.errorBanner}>
            <span>⚠</span> {error}
          </div>
        )}

        {/* Saved Traces */}
        <section>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>My Traces</h2>
            <span className={styles.count}>{traces.length} saved</span>
          </div>
          {traces.length === 0 ? (
            <div className={styles.emptyState}>
              <svg
                width="40"
                height="40"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#484f58"
                strokeWidth="1.5"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <p>No traces saved yet.</p>
              <p className={styles.emptyHint}>
                Paste a function and click &quot;Save&quot; to get started.
              </p>
            </div>
          ) : (
            <div className={styles.traceGrid}>
              {traces.map(trace => (
                <div key={trace.id} className={styles.traceCard}>
                  <pre className={styles.codePreview}>
                    <code>{truncateCode(trace.code)}</code>
                  </pre>
                  <div className={styles.traceTags}>
                    {(trace.concept_tags ?? []).slice(0, 3).map(tag => (
                      <span key={tag} className={styles.tag}>
                        {tag}
                      </span>
                    ))}
                  </div>
                  <div className={styles.traceFooter}>
                    <span className={styles.traceDate}>{timeAgo(trace.created_at)}</span>
                    <div className={styles.traceActions}>
                      <Link href={`/trace/${trace.share_token}`} className={styles.actionBtn}>
                        Open
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Review Queue */}
        <section>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Review Queue</h2>
            <div className={styles.streakBadge}>
              {streak > 0 ? `🔥 ${streak}-day streak` : 'Start your streak!'}
            </div>
          </div>
          {dueCards.length === 0 ? (
            <div className={styles.emptyState}>
              <svg
                width="40"
                height="40"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#484f58"
                strokeWidth="1.5"
              >
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <p>No reviews due.</p>
              <p className={styles.emptyHint}>Trace some code to build your review queue.</p>
            </div>
          ) : (
            <div className={styles.cardGrid}>
              {dueCards.map(card => (
                <div key={card.id} className={styles.reviewCard}>
                  <div className={styles.reviewCardHeader}>
                    <span className={styles.conceptTag}>{card.concept_tag}</span>
                    <span className={styles.dueLabel}>
                      {formatNextReview(new Date(card.next_review_date))}
                    </span>
                  </div>
                  <div className={styles.reviewCardMeta}>
                    {card.interval_days === 1 ? 'New card' : `Reviewed ${card.repetitions}×`}
                  </div>
                  <Link href={`/review/${card.id}`} className={styles.reviewBtn}>
                    Review Now
                  </Link>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
