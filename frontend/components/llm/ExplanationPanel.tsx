"use client";

import { useState, useCallback } from "react";
import { useStreamingExplanation } from "@/hooks/useStreamingExplanation";
import styles from "./ExplanationPanel.module.css";

interface ExplanationPanelProps {
  code: string;
  lineNumber: number;
  lineContent: string;
  locals: Record<string, { type: string; value: string }>;
  onClose?: () => void;
}

export function ExplanationPanel({
  code,
  lineNumber,
  lineContent,
  locals,
  onClose,
}: ExplanationPanelProps) {
  const { text, state, error, provider, start, stop, retry } =
    useStreamingExplanation();

  const [rating, setRating] = useState<number | null>(null);

  const submitRating = useCallback(async (stars: number) => {
    setRating(stars);
    // Submit rating to backend
    try {
      await fetch("/api/ratings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          explanation_id: null,
          trace_id: null,
          rating: stars,
        }),
      });
    } catch (err) {
      console.error("Failed to submit rating:", err);
    }
  }, []);

  const isLoading = state === "connecting" || state === "streaming";

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.icon}>💡</span>
          <h3 className={styles.title}>Why is this here?</h3>
        </div>
        <div className={styles.headerRight}>
          {provider && (
            <span className={styles.providerBadge}>
              via {provider === "ollama_cloud" ? "Ollama Cloud" : provider}
            </span>
          )}
          {onClose && (
            <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Code context */}
      <div className={styles.contextBlock}>
        <code className={styles.lineContext}>
          Line {lineNumber}: <span className={styles.lineText}>{lineContent}</span>
        </code>
      </div>

      {/* Stream content */}
      <div className={styles.content}>
        {isLoading && text === "" && (
          <div className={styles.loadingState}>
            <span className={styles.thinkingDots}>
              <span>.</span>
              <span>.</span>
              <span>.</span>
            </span>
            <span className={styles.loadingText}>Analyzing execution context...</span>
          </div>
        )}

        {text && (
          <div className={styles.explanation}>
            <p>{text}</p>
          </div>
        )}

        {/* Blinking cursor while streaming */}
        {state === "streaming" && text.length > 0 && (
          <span className={styles.cursor}>▌</span>
        )}

        {error && (
          <div className={styles.error}>
            <p>{error}</p>
            <div className={styles.errorActions}>
              <button className={styles.retryBtn} onClick={retry}>
                Try Again
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Rating widget — shown after streaming completes */}
      {state === "done" && (
        <div className={styles.ratingWidget}>
          <p className={styles.ratingPrompt}>Was this explanation helpful?</p>
          <div className={styles.ratingStars}>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                className={styles.starBtn}
                onClick={() => submitRating(n)}
                aria-label={`Rate ${n} stars`}
                disabled={rating !== null}
              >
                {rating !== null && n <= rating ? "★" : "☆"}
              </button>
            ))}
          </div>
          {rating !== null && (
            <p className={styles.ratingConfirm}>Thanks for your feedback!</p>
          )}
        </div>
      )}

      {/* Action bar */}
      <div className={styles.actionBar}>
        <button
          className={styles.askBtn}
          onClick={() =>
            start({ code, line_number: lineNumber, line_content: lineContent, locals })
          }
          disabled={isLoading}
        >
          {state === "streaming" ? "⏳ Generating..." : "Generate Explanation"}
        </button>
      </div>
    </div>
  );
}
