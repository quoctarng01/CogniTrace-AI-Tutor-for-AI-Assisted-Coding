'use client';

import { useState, useCallback, useEffect } from 'react';
import { useStreamingExplanation } from '@/hooks/useStreamingExplanation';
import { api, submitExplanationRating, Profile } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import styles from './ExplanationPanel.module.css';

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
  const { token, isAuthenticated } = useAuth();
  const { text, state, error, provider, start, stop, retry } = useStreamingExplanation();

  const [rating, setRating] = useState<number | null>(null);
  const [userPlan, setUserPlan] = useState<'free' | 'pro'>('free');
  const [isLocalMode, setIsLocalMode] = useState(false);
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [showOllamaHelp, setShowOllamaHelp] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      api.setToken(token);
      api.getProfile()
        .then(profile => {
          const plan = profile.plan ?? 'free';
          setUserPlan(plan);
          if (plan === 'free') {
            setIsLocalMode(true);
          }
        })
        .catch(err => {
          console.error('Failed to fetch profile plan:', err);
        });
    } else {
      setUserPlan('free');
      setIsLocalMode(true);
    }
  }, [isAuthenticated, token]);

  const submitRating = useCallback(async (stars: number) => {
    setRating(stars);
    // Submit rating to backend
    try {
      await submitExplanationRating({
        explanation_id: null,
        trace_id: null,
        rating: stars,
      });
    } catch (err) {
      console.error('Failed to submit rating:', err);
    }
  }, []);

  const handleStartExplanation = useCallback(() => {
    start({
      code,
      line_number: lineNumber,
      line_content: lineContent,
      locals,
      ollama_endpoint: isLocalMode ? ollamaUrl : undefined,
      token,
    });
  }, [code, lineNumber, lineContent, locals, isLocalMode, ollamaUrl, token, start]);

  const isLoading = state === 'connecting' || state === 'streaming';

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
              via {provider === 'ollama_cloud' ? 'Ollama Cloud' : provider}
            </span>
          )}
          {onClose && (
            <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Mode Switcher Toggle */}
      <div className={styles.modeToggle}>
        <button
          className={`${styles.modeBtn} ${!isLocalMode ? styles.activeMode : ''}`}
          onClick={() => setIsLocalMode(false)}
          disabled={isLoading}
        >
          ☁️ Cloud AI {userPlan === 'free' && '(Rate Limit)'}
        </button>
        <button
          className={`${styles.modeBtn} ${isLocalMode ? styles.activeMode : ''}`}
          onClick={() => setIsLocalMode(true)}
          disabled={isLoading}
        >
          ⚡ Local AI (Ollama)
        </button>
      </div>

      {/* Free Plan Cloud Warning */}
      {userPlan === 'free' && !isLocalMode && (
        <div className={styles.freePlanWarning}>
          ℹ️ <strong>Free Plan limits apply</strong>. Cloud AI has rate limits. Log in to a whitelisted examiner account or switch to **Local AI** for unlimited, free usage.
        </div>
      )}

      {/* Local Mode Configuration */}
      {isLocalMode && (
        <div className={styles.localConfig}>
          <div className={styles.endpointField}>
            <label className={styles.endpointLabel}>Ollama URL:</label>
            <input
              type="text"
              value={ollamaUrl}
              onChange={e => setOllamaUrl(e.target.value)}
              className={styles.endpointInput}
              placeholder="http://localhost:11434"
              disabled={isLoading}
            />
          </div>
          <button
            type="button"
            className={styles.helpToggle}
            onClick={() => setShowOllamaHelp(prev => !prev)}
          >
            {showOllamaHelp ? 'Hide Setup Help ▲' : 'Show Setup Help ▼'}
          </button>

          {showOllamaHelp && (
            <div className={styles.helpBlock}>
              <p>To run Ollama locally on your machine:</p>
              <ol className={styles.helpSteps}>
                <li>Download and install <a href="https://ollama.com" target="_blank" rel="noreferrer" className={styles.link}>Ollama</a>.</li>
                <li>Start Ollama and pull the Llama model in your terminal:
                  <pre className={styles.preCode}>ollama run llama3.2</pre>
                </li>
                <li>Keep the Ollama app running and generate explanations!</li>
              </ol>
            </div>
          )}
        </div>
      )}

      {/* Code context */}
      <div className={styles.contextBlock}>
        <code className={styles.lineContext}>
          Line {lineNumber}: <span className={styles.lineText}>{lineContent}</span>
        </code>
      </div>

      {/* Stream content */}
      <div className={styles.content}>
        {isLoading && text === '' && (
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
        {state === 'streaming' && text.length > 0 && <span className={styles.cursor}>▌</span>}

        {error && (
          <div className={styles.error}>
            <p>{error}</p>
            {error.includes('Rate limit exceeded') && (
              <p className={styles.errorHint}>
                💡 Switch to <strong>Local AI (Ollama)</strong> above to get unlimited explanations.
              </p>
            )}
            <div className={styles.errorActions}>
              <button className={styles.retryBtn} onClick={retry}>
                Try Again
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Rating widget — shown after streaming completes */}
      {state === 'done' && (
        <div className={styles.ratingWidget}>
          <p className={styles.ratingPrompt}>Was this explanation helpful?</p>
          <div className={styles.ratingStars}>
            {[1, 2, 3, 4, 5].map(n => (
              <button
                key={n}
                className={styles.starBtn}
                onClick={() => submitRating(n)}
                aria-label={`Rate ${n} stars`}
                disabled={rating !== null}
              >
                {rating !== null && n <= rating ? '★' : '☆'}
              </button>
            ))}
          </div>
          {rating !== null && <p className={styles.ratingConfirm}>Thanks for your feedback!</p>}
        </div>
      )}

      {/* Action bar */}
      <div className={styles.actionBar}>
        <button
          className={styles.askBtn}
          onClick={handleStartExplanation}
          disabled={isLoading}
        >
          {state === 'streaming' ? '⏳ Generating...' : 'Generate Explanation'}
        </button>
      </div>
    </div>
  );
}
