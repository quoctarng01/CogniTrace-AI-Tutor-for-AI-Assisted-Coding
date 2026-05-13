// frontend/app/review/[card_id]/page.tsx
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { getSupabase } from "@/lib/supabase";
import { fetchReviewCard, submitReviewRating } from "@/lib/api";
import { formatNextReview } from "@/lib/sm2";
import type { ReviewCardDetail } from "@/types/user";
import type { TraceStep } from "@/types/trace";
import styles from "./review.module.css";

const CodeEditor = dynamic(
  () => import("@/components/editor/CodeEditor").then((m) => m.CodeEditor),
  { ssr: false, loading: () => <div className={styles.editorLoading}>Loading code...</div> }
);

type ReviewState = "loading" | "playing" | "rating" | "submitting" | "submitted" | "error";
const INTERVAL_MS = 750;

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const cardId = params.card_id as string;

  const [card, setCard] = useState<ReviewCardDetail | null>(null);
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [currentStep, setCurrentStep] = useState(0);
  const [reviewState, setReviewState] = useState<ReviewState>("loading");
  const [rating, setRating] = useState<"again" | "hard" | "good" | "easy" | null>(null);
  const [nextReview, setNextReview] = useState<string | null>(null);
  const [nextInterval, setNextInterval] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rafRef = useRef<number | null>(null);
  const lastTimestampRef = useRef<number | null>(null);
  const playingRef = useRef(false);

  // Load single card with trace + steps in one API call
  useEffect(() => {
    async function load() {
      const { data } = await getSupabase().auth.getSession();
      if (!data?.session) { router.replace("/auth/login"); return; }
      try {
        const data = await fetchReviewCard(cardId);
        setCard(data);
        setSteps(data.trace.steps ?? []);
        setReviewState("playing");
      } catch (err) {
        if (err instanceof Error && err.message === "CARD_NOT_FOUND") {
          setError("Card not found. It may have already been reviewed.");
        } else if (err instanceof Error && err.message === "AUTH_REQUIRED") {
          router.replace("/auth/login");
        } else {
          setError(err instanceof Error ? err.message : "Failed to load card");
        }
        setReviewState("error");
      }
    }
    load();
  }, [cardId, router]);

  // Auto-play animation
  const startAnimation = useCallback((stepsToPlay: TraceStep[]) => {
    if (stepsToPlay.length === 0) { setReviewState("rating"); return; }
    playingRef.current = true;
    setCurrentStep(0);

    function tick(timestamp: number) {
      if (!playingRef.current) return;
      if (lastTimestampRef.current === null) lastTimestampRef.current = timestamp;
      const elapsed = timestamp - lastTimestampRef.current;

      if (elapsed >= INTERVAL_MS) {
        setCurrentStep((prev) => {
          if (prev + 1 >= stepsToPlay.length) {
            playingRef.current = false;
            lastTimestampRef.current = null;
            setReviewState("rating");
            return prev;
          }
          lastTimestampRef.current = timestamp;
          return prev + 1;
        });
        return;
      }
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
  }, []);

  // Trigger auto-play once card loads
  useEffect(() => {
    if (reviewState !== "playing") return;
    const timer = setTimeout(() => {
      startAnimation(steps.length > 0 ? steps : []);
    }, 800);
    return () => clearTimeout(timer);
  }, [reviewState]);

  // Cleanup rAF on unmount
  useEffect(() => {
    return () => {
      playingRef.current = false;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const handleRating = useCallback(async (r: "again" | "hard" | "good" | "easy") => {
    setRating(r);
    setReviewState("submitting");
    try {
      const result = await submitReviewRating(cardId, r);
      setNextReview(result.next_review_date);
      setNextInterval(result.new_interval_days);
      setReviewState("submitted");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit review");
      setReviewState("rating"); // return to rating so user can retry
    }
  }, [cardId]);

  if (reviewState === "loading") {
    return <div className={styles.page}><div className={styles.loading}><span className={styles.spinner}>◈</span> Loading review...</div></div>;
  }

  if (reviewState === "error") {
    return (
      <div className={styles.page}>
        <div className={styles.errorState}>
          <p>⚠ {error}</p>
          <Link href="/dashboard" className={styles.backBtn}>← Back to dashboard</Link>
        </div>
      </div>
    );
  }

  const currentStepData = steps[currentStep] ?? null;

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Link href="/dashboard" className={styles.backLink}>← Dashboard</Link>
        <div className={styles.cardInfo}>
          {card && <span className={styles.conceptTag}>{card.concept_tag}</span>}
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

        {reviewState === "playing" && steps.length > 0 && (
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }} />
          </div>
        )}

        {(reviewState === "rating" || reviewState === "submitting") && (
          <div className={styles.ratingPanel}>
            <h2 className={styles.ratingTitle}>
              {reviewState === "submitting" ? "Submitting..." : "How well did you understand this?"}
            </h2>
            <div className={styles.ratingButtons}>
              {(["again", "hard", "good", "easy"] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => handleRating(r)}
                  disabled={reviewState === "submitting" || rating !== null}
                  className={`${styles.ratingBtn} ${styles[`ratingBtn_${r}`]}`}
                >
                  <span className={styles.ratingLabel}>
                    {r === "again" ? "Again" : r === "hard" ? "Hard" : r === "good" ? "Good" : "Easy"}
                  </span>
                  <span className={styles.ratingHint}>
                    {r === "again" ? "Forgot it" : r === "hard" ? "Struggled" : r === "good" ? "Got it" : "Too easy"}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {reviewState === "submitted" && (
          <div className={styles.submittedPanel}>
            <div className={styles.submittedIcon}>✓</div>
            <h2 className={styles.submittedTitle}>Review complete!</h2>
            {nextReview && nextInterval !== null && (
              <p className={styles.submittedInfo}>
                Next review: <strong>{formatNextReview(new Date(nextReview))}</strong>
                {" "}({nextInterval === 1 ? "1 day" : `${nextInterval} days`})
              </p>
            )}
            <button onClick={() => router.push("/dashboard")} className={styles.dashboardBtn}>
              ← Back to Dashboard
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
