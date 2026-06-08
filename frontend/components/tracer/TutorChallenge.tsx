'use client';

import { useState, useCallback } from 'react';
import type { TraceCheckpoint, TraceStep } from '@/types/trace';
import { authFetch } from '@/lib/api';
import styles from './TutorChallenge.module.css';

interface TutorChallengeProps {
  checkpoint: TraceCheckpoint;
  code: string;
  steps: TraceStep[];
  traceId?: string | null;
  onSuccess: () => void;
}

interface DiagnoseResponse {
  tag: string;
  explanation: string;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000') + '/api';

export function TutorChallenge({ checkpoint, code, steps, traceId, onSuccess }: TutorChallengeProps) {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);
  const [isLoadingDiagnose, setIsLoadingDiagnose] = useState(false);
  const [diagnoseResult, setDiagnoseResult] = useState<DiagnoseResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async (option: string) => {
    if (isSubmitted) return;
    setSelectedOption(option);
    setIsSubmitted(true);

    const correct = option === checkpoint.correct_value;
    setIsCorrect(correct);

    if (correct) {
      // Correct! The user continues.
      return;
    }

    // Incorrect: Call LLM to diagnose misconception
    setIsLoadingDiagnose(true);
    setError(null);
    try {
      const payload = {
        code,
        checkpoint_type: checkpoint.checkpoint_type,
        variable_name: checkpoint.variable_name,
        correct_value: checkpoint.correct_value,
        user_prediction: option,
        line_number: checkpoint.line_number,
        trace_id: traceId || null,
        steps: steps, // Pass current trace steps for auto-saving
      };

      const res = await authFetch(`${API_BASE}/llm/diagnose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error('Failed to fetch explanation from AI Tutor');
      }

      const data: DiagnoseResponse = await res.json();
      setDiagnoseResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reach AI Tutor');
    } finally {
      setIsLoadingDiagnose(false);
    }
  }, [checkpoint, code, steps, traceId, isSubmitted]);

  return (
    <div className={styles.container}>
      <div className={`${styles.card} ${isSubmitted ? (isCorrect ? styles.correctGlow : styles.incorrectGlow) : ''}`}>
        <div className={styles.header}>
          <span className={styles.badge}>◈ AI TUTOR CHALLENGE</span>
          <h3 className={styles.title}>Predict the Next State</h3>
        </div>

        <p className={styles.prompt}>{checkpoint.prompt}</p>

        {!isSubmitted ? (
          <div className={styles.optionsList}>
            {checkpoint.options.map((option, idx) => (
              <button
                key={idx}
                className={styles.optionBtn}
                onClick={() => handleSubmit(option)}
              >
                {option}
              </button>
            ))}
          </div>
        ) : (
          <div className={styles.resultSection}>
            {isCorrect ? (
              <div className={styles.successBox}>
                <span className={styles.statusIcon}>✓</span>
                <p className={styles.statusText}>Excellent! Your prediction is correct.</p>
                <button className={styles.actionBtn} onClick={onSuccess}>
                  Continue Trace
                </button>
              </div>
            ) : (
              <div className={styles.failureBox}>
                <span className={styles.statusIcon}>✕</span>
                <p className={styles.statusText}>
                  Your prediction was different: <code>{selectedOption}</code> (Expected: <code>{checkpoint.correct_value}</code>)
                </p>

                {isLoadingDiagnose && (
                  <div className={styles.diagnoseLoader}>
                    <span className={styles.spinner}>◈</span> Diagnosing misconception...
                  </div>
                )}

                {diagnoseResult && (
                  <div className={styles.feedbackCard}>
                    <span className={styles.misconceptionTag}>
                      Concept Gap: {diagnoseResult.tag.replace(/_/g, ' ')}
                    </span>
                    <p className={styles.explanationText}>
                      {diagnoseResult.explanation}
                    </p>
                  </div>
                )}

                {error && <p className={styles.errorText}>⚠ {error}</p>}

                <button className={styles.actionBtn} onClick={onSuccess} disabled={isLoadingDiagnose}>
                  Acknowledge & Continue
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
