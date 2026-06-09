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
  const [customPat, setCustomPat] = useState('');
  const [customApiUrl, setCustomApiUrl] = useState('');
  const [customApiKey, setCustomApiKey] = useState('');
  const [customApiModel, setCustomApiModel] = useState('');
  const [patSaveStatus, setPatSaveStatus] = useState('');

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
          if (profile.github_models_pat) {
            setCustomPat(profile.github_models_pat);
          }
          if (profile.custom_api_url) {
            setCustomApiUrl(profile.custom_api_url);
          }
          if (profile.custom_api_key) {
            setCustomApiKey(profile.custom_api_key);
          }
          if (profile.custom_api_model) {
            setCustomApiModel(profile.custom_api_model);
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

  const handleSaveConfig = useCallback(async () => {
    try {
      setPatSaveStatus('Saving...');
      await api.updateProfile({
        github_models_pat: customPat.trim() || null,
        custom_api_url: customApiUrl.trim() || null,
        custom_api_key: customApiKey.trim() || null,
        custom_api_model: customApiModel.trim() || null,
      });
      setPatSaveStatus('Saved successfully!');
      setTimeout(() => setPatSaveStatus(''), 3000);
    } catch (err) {
      console.error('Failed to save config:', err);
      setPatSaveStatus('Failed to save settings.');
    }
  }, [customPat, customApiUrl, customApiKey, customApiModel]);

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
              via {provider === 'ollama_cloud' ? 'Ollama Cloud' : provider === 'custom_openai' ? 'Custom OpenAI' : provider}
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

      {/* Free Plan Cloud Warning & Custom PAT/API options */}
      {!isLocalMode && (
        <div className={styles.localConfig}>
          {userPlan === 'free' && (
            <div className={styles.freePlanWarning} style={{ margin: '0 0 10px 0' }}>
              ℹ️ <strong>Free Plan limits apply</strong>. Cloud AI has rate limits. Log in to a whitelisted examiner account or configure your own GitHub PAT or OpenAI-compatible endpoint below.
            </div>
          )}
          {isAuthenticated ? (
            <div className={styles.configContainer}>
              <div className={styles.configSection}>
                <h4 className={styles.sectionTitle}>Option A: GitHub Models</h4>
                <div className={styles.endpointField}>
                  <label className={styles.endpointLabel}>GitHub PAT:</label>
                  <input
                    type="password"
                    value={customPat}
                    onChange={e => setCustomPat(e.target.value)}
                    className={styles.endpointInput}
                    placeholder="Paste custom ghp_... API key"
                    disabled={isLoading}
                  />
                </div>
              </div>

              <div className={styles.sectionDivider} />

              <div className={styles.configSection}>
                <h4 className={styles.sectionTitle}>Option B: Custom OpenAI API</h4>
                <div className={styles.endpointField}>
                  <label className={styles.endpointLabel}>API URL:</label>
                  <input
                    type="text"
                    value={customApiUrl}
                    onChange={e => setCustomApiUrl(e.target.value)}
                    className={styles.endpointInput}
                    placeholder="https://api.openai.com/v1"
                    disabled={isLoading}
                  />
                </div>
                <div className={styles.endpointField}>
                  <label className={styles.endpointLabel}>API Key:</label>
                  <input
                    type="password"
                    value={customApiKey}
                    onChange={e => setCustomApiKey(e.target.value)}
                    className={styles.endpointInput}
                    placeholder="Paste custom API key"
                    disabled={isLoading}
                  />
                </div>
                <div className={styles.endpointField}>
                  <label className={styles.endpointLabel}>Model Name:</label>
                  <input
                    type="text"
                    value={customApiModel}
                    onChange={e => setCustomApiModel(e.target.value)}
                    className={styles.endpointInput}
                    placeholder="gpt-4o-mini"
                    disabled={isLoading}
                  />
                </div>
              </div>

              <div className={styles.actionsRow}>
                <button
                  type="button"
                  className={styles.saveBtn}
                  onClick={handleSaveConfig}
                  disabled={isLoading}
                >
                  Save Config
                </button>
                {patSaveStatus && <span className={styles.saveStatus}>{patSaveStatus}</span>}
              </div>
            </div>
          ) : (
            <div className={styles.freePlanWarning} style={{ margin: 0 }}>
              💡 Sign in to set custom keys and bypass standard rate limits.
            </div>
          )}
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
