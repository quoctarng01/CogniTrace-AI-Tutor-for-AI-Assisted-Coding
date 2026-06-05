// frontend/app/review/[card_id]/page.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { getSupabase } from '@/lib/supabase';
import { fetchReviewCard, submitReviewRating } from '@/lib/api';
import { formatNextReview } from '@/lib/sm2';
import type { ReviewCardDetail } from '@/types/user';
import { useTrace } from '@/hooks/useTrace';
import styles from './review.module.css';

const CodeEditor = dynamic(() => import('@/components/editor/CodeEditor').then(m => m.CodeEditor), {
  ssr: false,
  loading: () => <div className={styles.editorLoading}>Loading code...</div>,
});

type ReviewState = 'loading' | 'playing' | 'rating' | 'submitting' | 'submitted' | 'error';

const RATING_CONFIG: Record<'again' | 'hard' | 'good' | 'easy', { label: string; hint: string }> = {
  again: { label: 'Again', hint: 'Forgot it' },
  hard: { label: 'Hard', hint: 'Struggled' },
  good: { label: 'Good', hint: 'Got it' },
  easy: { label: 'Easy', hint: 'Too easy' },
};

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const cardId = params.card_id as string;

  const [card, setCard] = useState<ReviewCardDetail | null>(null);
  const [reviewState, setReviewState] = useState<ReviewState>('loading');
  const [rating, setRating] = useState<'again' | 'hard' | 'good' | 'easy' | null>(null);
  const [nextReview, setNextReview] = useState<string | null>(null);
  const [nextInterval, setNextInterval] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // REPLAY: Use saved steps from the card (NOT re-execution).
  // Backend returns card.trace.steps from the traces.steps JSONB column.
  const steps = card?.trace?.steps ?? [];

  // useTrace manages animation state — same hook as tracer page
  const {
    currentStep,
    playbackState,
    currentStepData,
    togglePlayPause,
    stepForward,
    stepBackward,
    jumpToStep,
    setSpeed,
    reset,
  } = useTrace({ steps, autoPlay: true });

  // Load card on mount
  useEffect(() => {
    async function load() {
      const { data } = await getSupabase().auth.getSession();
      if (!data?.session) {
        router.replace('/auth/login');
        return;
      }
      try {
        const loadedCard = await fetchReviewCard(cardId);
        setCard(loadedCard);
        setReviewState('playing');
      } catch (err) {
        if (err instanceof Error && err.message === 'CARD_NOT_FOUND') {
          setError('Card not found. It may have already been reviewed.');
        } else if (err instanceof Error && err.message === 'AUTH_REQUIRED') {
          router.replace('/auth/login');
        } else {
          setError(err instanceof Error ? err.message : 'Failed to load card');
        }
        setReviewState('error');
      }
    }
    load();
  }, [cardId, router]);

  // Transition from playing → rating when playback ends
  useEffect(() => {
    if (playbackState === 'ended' && reviewState === 'playing') {
      setReviewState('rating');
    }
  }, [playbackState, reviewState]);

  const handleRating = useCallback(
    async (r: 'again' | 'hard' | 'good' | 'easy') => {
      setRating(r);
      setReviewState('submitting');
      try {
        const result = await submitReviewRating(cardId, r);
        setNextReview(result.next_review_date);
        setNextInterval(result.new_interval_days);
        setReviewState('submitted');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to submit review');
        setReviewState('rating'); // Return to rating so user can retry
      }
    },
    [cardId]
  );

  if (reviewState === 'loading') {
    return (
      <div className={styles.page}>
        <div className={styles.loading}>
          <span className={styles.spinner}>◈</span> Loading review...
        </div>
      </div>
    );
  }

  if (reviewState === 'error') {
    return (
      <div className={styles.page}>
        <div className={styles.errorState}>
          <p>⚠ {error}</p>
          <Link href="/dashboard" className={styles.backBtn}>
            ← Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Link href="/dashboard" className={styles.backLink}>
          ← Dashboard
        </Link>
        <div className={styles.cardInfo}>
          {card && <span className={styles.conceptTag}>{card.concept_tag}</span>}
          <span className={styles.replayBadge}>🔁 Replay</span>
        </div>
        <div />
      </header>

      <main className={styles.main}>
        <div className={styles.editorSection}>
          {card ? (
            <CodeEditor
              code={card.trace.code}
              onChange={() => {}}
              currentLine={currentStepData?.line_number ?? 1}
              readOnly
            />
          ) : (
            <div className={styles.noCode}>
              <p>Trace code unavailable.</p>
              <p className={styles.hint}>The trace may have been deleted.</p>
            </div>
          )}
        </div>

        {/* Manual step controls during playback */}
        {reviewState === 'playing' && steps.length > 0 && (
          <>
            <div className={styles.stepCounter}>
              Step {currentStep + 1} / {steps.length}
            </div>
            <div className={styles.controlsRow}>
              <button onClick={stepBackward} disabled={currentStep === 0}>⏮</button>
              <button onClick={togglePlayPause}>
                {playbackState === 'playing' ? '⏸' : '▶'}
              </button>
              <button onClick={stepForward} disabled={currentStep >= steps.length - 1}>⏭</button>
            </div>
          </>
        )}

        {/* Rating buttons */}
        {(reviewState === 'rating' || reviewState === 'submitting') && (
          <div className={styles.ratingPanel}>
            <h2 className={styles.ratingTitle}>
              {reviewState === 'submitting'
                ? 'Submitting...'
                : 'How well did you understand this?'}
            </h2>
            <div className={styles.ratingButtons}>
              {(['again', 'hard', 'good', 'easy'] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => handleRating(r)}
                  disabled={reviewState === 'submitting' || rating !== null}
                  className={`${styles.ratingBtn} ${styles[`ratingBtn_${r}`]}`}
                >
                  <span className={styles.ratingLabel}>{RATING_CONFIG[r].label}</span>
                  <span className={styles.ratingHint}>{RATING_CONFIG[r].hint}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Submitted state */}
        {reviewState === 'submitted' && (
          <div className={styles.submittedPanel}>
            <div className={styles.submittedIcon}>✓</div>
            <h2 className={styles.submittedTitle}>Review complete!</h2>
            {nextReview && nextInterval !== null && (
              <p className={styles.submittedInfo}>
                Next review: <strong>{formatNextReview(new Date(nextReview))}</strong> (
                {nextInterval === 1 ? '1 day' : `${nextInterval} days`})
              </p>
            )}
            <button
              onClick={() => router.push('/dashboard')}
              className={styles.dashboardBtn}
            >
              ← Back to Dashboard
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
