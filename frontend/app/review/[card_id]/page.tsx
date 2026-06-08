// frontend/app/review/[card_id]/page.tsx
'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { getSupabase } from '@/lib/supabase';
import { fetchReviewCard, submitReviewRating, gradeReviewExplanation, type GradeReviewResponse } from '@/lib/api';
import { formatNextReview } from '@/lib/sm2';
import type { ReviewCardDetail } from '@/types/user';
import { useTrace } from '@/hooks/useTrace';
import { trackEvent } from '@/lib/analytics';
import styles from './review.module.css';

const CodeEditor = dynamic(() => import('@/components/editor/CodeEditor').then(m => m.CodeEditor), {
  ssr: false,
  loading: () => <div className={styles.editorLoading}>Loading code...</div>,
});

type ReviewState = 'loading' | 'playing' | 'active_recall' | 'grading' | 'rating' | 'submitting' | 'submitted' | 'error';

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

  const [activeRecallText, setActiveRecallText] = useState('');
  const [gradingResult, setGradingResult] = useState<GradeReviewResponse | null>(null);
  const [isGrading, setIsGrading] = useState(false);

  const cardRef = useRef<ReviewCardDetail | null>(null);

  useEffect(() => {
    cardRef.current = card;
  }, [card]);

  // ── Track session time-on-task ───────────────────────────────────
  useEffect(() => {
    trackEvent('review_session_started', { card_id: cardId });
    const startTime = Date.now();
    return () => {
      const durationSeconds = (Date.now() - startTime) / 1000;
      trackEvent('review_session_ended', {
        card_id: cardId,
        duration_seconds: durationSeconds,
        concept_tag: cardRef.current?.concept_tag,
      });
    };
  }, [cardId]);

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
        if (loadedCard.code_repair_challenge) {
          setReviewState('active_recall');
        } else {
          setReviewState('playing');
        }
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

  // Transition from playing → active_recall when playback ends
  useEffect(() => {
    if (playbackState === 'ended' && reviewState === 'playing') {
      setReviewState('active_recall');
    }
  }, [playbackState, reviewState]);

  const handleGrade = useCallback(async () => {
    if (!activeRecallText.trim()) return;
    setIsGrading(true);
    setReviewState('grading');
    setError(null);
    trackEvent('review_grading_started', { card_id: cardId });
    try {
      const result = await gradeReviewExplanation(cardId, activeRecallText);
      setGradingResult(result);
      setReviewState('rating');
      trackEvent('review_grading_completed', {
        card_id: cardId,
        score: result.score,
        rating_suggestion: result.rating_suggestion,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Grading failed');
      setReviewState('active_recall');
      trackEvent('review_grading_failed', {
        card_id: cardId,
        error: err instanceof Error ? err.message : 'Grading failed',
      });
    } finally {
      setIsGrading(false);
    }
  }, [cardId, activeRecallText]);

  const handleRating = useCallback(
    async (r: 'again' | 'hard' | 'good' | 'easy') => {
      setRating(r);
      setReviewState('submitting');
      trackEvent('review_rating_submitted', {
        card_id: cardId,
        rating: r,
        concept_tag: cardRef.current?.concept_tag,
      });
      try {
        const result = await submitReviewRating(cardId, r);
        setNextReview(result.next_review_date);
        setNextInterval(result.new_interval_days);
        setReviewState('submitted');
        trackEvent('review_rating_saved', {
          card_id: cardId,
          rating: r,
          new_interval_days: result.new_interval_days,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to submit review');
        setReviewState('rating'); // Return to rating so user can retry
        trackEvent('review_rating_failed', {
          card_id: cardId,
          error: err instanceof Error ? err.message : 'Failed to submit',
        });
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
              code={card.code_repair_challenge ?? card.trace.code}
              onChange={() => {}}
              currentLine={card.code_repair_challenge ? undefined : (currentStepData?.line_number ?? 1)}
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
              <button
                onClick={() => {
                  stepBackward();
                  trackEvent('review_step_navigated', { direction: 'backward', current_step: currentStep - 1, card_id: cardId });
                }}
                disabled={currentStep === 0}
              >
                ⏮
              </button>
              <button
                onClick={() => {
                  togglePlayPause();
                  trackEvent('review_playback_toggled', { current_step: currentStep, state: playbackState, card_id: cardId });
                }}
              >
                {playbackState === 'playing' ? '⏸' : '▶'}
              </button>
              <button
                onClick={() => {
                  stepForward();
                  trackEvent('review_step_navigated', { direction: 'forward', current_step: currentStep + 1, card_id: cardId });
                }}
                disabled={currentStep >= steps.length - 1}
              >
                ⏭
              </button>
            </div>
          </>
        )}

        {/* Active Recall textbox */}
        {reviewState === 'active_recall' && (
          <div className={styles.activeRecallPanel}>
            <h2 className={styles.ratingTitle}>
              {card?.code_repair_challenge ? 'Tutor Challenge: Code Repair' : 'Active Recall Challenge'}
            </h2>
            <p className={styles.recallLabel}>
              {card?.code_repair_challenge
                ? 'Spot the logical bug in the code on the left and write the corrected Python code below.'
                : 'Explain step-by-step how this code executed and why variables updated the way they did.'}
            </p>
            <textarea
              className={styles.recallTextarea}
              placeholder={
                card?.code_repair_challenge
                  ? 'Paste or write the corrected code here...'
                  : 'Type your explanation here... (e.g., n started at 8, we looped until it was 1...)'
              }
              value={activeRecallText}
              onChange={(e) => setActiveRecallText(e.target.value)}
            />
            <button
              onClick={handleGrade}
              disabled={!activeRecallText.trim()}
              className={styles.submitExplanationBtn}
            >
              Submit to AI Tutor
            </button>
          </div>
        )}

        {/* Grading state */}
        {reviewState === 'grading' && (
          <div className={styles.gradingPanel}>
            <div className={styles.loading}>
              <span className={styles.spinner}>◈</span> Grading your answer via AI Tutor...
            </div>
          </div>
        )}

        {/* Rating buttons */}
        {(reviewState === 'rating' || reviewState === 'submitting') && (
          <div className={styles.ratingPanel}>
            {gradingResult && (
              <div className={styles.feedbackSection}>
                <div className={styles.feedbackHeader}>
                  <span className={styles.feedbackTitle}>AI Tutor Assessment</span>
                  <span className={styles.scoreBadge}>Score: {gradingResult.score}%</span>
                </div>
                <div className={styles.feedbackText}>{gradingResult.feedback}</div>
                <div className={styles.suggestionText}>
                  Suggested Rating: <strong>{RATING_CONFIG[gradingResult.rating_suggestion].label}</strong>
                </div>
              </div>
            )}
            
            <h2 className={styles.ratingTitle}>
              {reviewState === 'submitting'
                ? 'Submitting...'
                : 'Confirm how well you understood this:'}
            </h2>
            <div className={styles.ratingButtons}>
              {(['again', 'hard', 'good', 'easy'] as const).map((r) => {
                const isSuggested = gradingResult?.rating_suggestion === r;
                return (
                  <button
                    key={r}
                    onClick={() => handleRating(r)}
                    disabled={reviewState === 'submitting' || rating !== null}
                    className={`${styles.ratingBtn} ${styles[`ratingBtn_${r}`]} ${
                      isSuggested ? styles.ratingBtn_suggested : ''
                    }`}
                  >
                    <span className={styles.ratingLabel}>{RATING_CONFIG[r].label}</span>
                    <span className={styles.ratingHint}>{RATING_CONFIG[r].hint}</span>
                  </button>
                );
              })}
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
