'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { api, saveTrace, shareTrace, runTrace as runTraceApi } from '@/lib/api';
import { getSupabase, getAuthToken } from '@/lib/supabase';
import { trackEvent } from '@/lib/analytics';
import type { TraceResult, TraceStep } from '@/types/trace';
import type { Annotation } from '@/types/annotation';
import { useTrace } from '@/hooks/useTrace';
import { VariablePanel } from '@/components/tracer/VariablePanel';
import { AnimationControls } from '@/components/tracer/AnimationControls';
import { ExplanationPanel } from '@/components/llm/ExplanationPanel';
import { WhatIfModal } from '@/components/tracer/WhatIfModal';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import {
  EditorErrorBoundary,
  VariablePanelErrorBoundary,
  ExplanationPanelErrorBoundary,
} from '@/components/errors/ErrorBoundary';
import styles from './page.module.css';

// Dynamic imports for client-side only components
const CodeEditor = dynamic(() => import('@/components/editor/CodeEditor').then(m => m.CodeEditor), {
  ssr: false,
  loading: () => <div className={styles.editorLoading}>Loading editor...</div>,
});

const SAMPLE_CODE = `def fibonacci(n):
    """Generate fibonacci sequence up to n."""
    if n <= 0:
        return []
    elif n == 1:
        return [0]

    result = []
    a, b = 0, 1

    for i in range(n):
        result.append(a)
        a, b = b, a + b

    return result

fib = fibonacci(8)
`;

function extractConceptTags(code: string): string[] {
  const tags: string[] = [];
  if (/def\s+\w+\(/.test(code)) tags.push('FUNCTION');
  if (/for\s/.test(code)) tags.push('LOOP');
  if (/while\s/.test(code)) tags.push('LOOP');
  if (/if\s/.test(code)) tags.push('CONDITIONAL');
  if (/class\s/.test(code)) tags.push('CLASS');
  if (/try\s|except\s/.test(code)) tags.push('EXCEPTION');
  if (/lambda\s/.test(code)) tags.push('LAMBDA');
  if (/\[.*for.*in.*\]/.test(code)) tags.push('COMPREHENSION');
  return tags.slice(0, 4);
}

export default function TracerPage() {
  const router = useRouter();
  const [code, setCode] = useState(SAMPLE_CODE);
  const [traceResult, setTraceResult] = useState<TraceResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedLine, setSelectedLine] = useState<number | null>(null);
  const [showExplanation, setShowExplanation] = useState(false);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const analyzeDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Share modal state
  const [showShareModal, setShowShareModal] = useState(false);
  const [shareResult, setShareResult] = useState<{
    share_token: string;
    share_url: string;
    expires_at: string | null;
    has_password: boolean;
  } | null>(null);
  const [shareError, setShareError] = useState<string | null>(null);
  const [isSharing, setIsSharing] = useState(false);
  const [sharePassword, setSharePassword] = useState('');
  const [expirationDays, setExpirationDays] = useState<number | null>(null);

  // What-If modal state
  const [showWhatIf, setShowWhatIf] = useState(false);
  const [whatIfLoading, setWhatIfLoading] = useState(false);

  const steps = traceResult?.steps ?? [];

  // useTrace hook manages animation state from parent
  const {
    currentStep,
    playbackState,
    speed,
    currentStepData,
    play,
    pause,
    togglePlayPause,
    stepForward,
    stepBackward,
    jumpToStep,
    setSpeed,
    reset,
  } = useTrace({ steps });

  // ── Check authentication on mount ─────────────────────────────────
  useEffect(() => {
    async function checkAuth() {
      const token = await getAuthToken();
      setIsAuthenticated(!!token);
    }
    checkAuth();
  }, []);

  // ── Track session time-on-task ───────────────────────────────────
  useEffect(() => {
    trackEvent('tracer_session_started');
    const startTime = Date.now();
    return () => {
      const durationSeconds = (Date.now() - startTime) / 1000;
      trackEvent('tracer_session_ended', { duration_seconds: durationSeconds });
    };
  }, []);

  // ── Debounced static analysis on code change ─────────────────────
  useEffect(() => {
    if (!code.trim()) {
      setAnnotations([]);
      return;
    }
    if (analyzeDebounceRef.current) clearTimeout(analyzeDebounceRef.current);
    analyzeDebounceRef.current = setTimeout(async () => {
      setIsAnalyzing(true);
      try {
        const result = await api.analyzeCode(code);
        setAnnotations(result.annotations);
      } catch {
        // Analysis errors are non-critical — silently clear
        setAnnotations([]);
      } finally {
        setIsAnalyzing(false);
      }
    }, 600);
    return () => {
      if (analyzeDebounceRef.current) clearTimeout(analyzeDebounceRef.current);
    };
  }, [code]);

  const handleSaveTrace = useCallback(async () => {
    if (!traceResult?.steps?.length) return;
    const { data } = await getSupabase().auth.getSession();
    if (!data?.session) {
      router.push('/auth/login');
      return;
    }
    setIsSaving(true);
    setError(null);
    setSaveSuccess(false);
    try {
      await saveTrace({ code, steps: traceResult.steps, concept_tags: extractConceptTags(code) });
      setSaveSuccess(true);
      trackEvent('trace_saved', {
        concept_tags: extractConceptTags(code),
        steps_count: traceResult.steps.length,
      });
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      if (err instanceof Error && err.message.includes('UPGRADE_REQUIRED')) {
        setError('Free plan limit reached. Upgrade to Pro to save more traces.');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to save');
      }
    } finally {
      setIsSaving(false);
    }
  }, [code, traceResult, router]);

  const handleShareClick = useCallback(() => {
    setShowShareModal(true);
    setShareResult(null);
    setShareError(null);
    setSharePassword('');
    setExpirationDays(null);
  }, []);

  const handleShareSubmit = useCallback(async () => {
    if (!traceResult?.trace_id) return;
    setIsSharing(true);
    setShareError(null);
    try {
      const result = await shareTrace(traceResult.trace_id, {
        expiration_days: expirationDays ?? undefined,
        password: sharePassword || undefined,
      });
      setShareResult(result);
      trackEvent('trace_shared', {
        expiration_days: expirationDays,
        has_password: !!sharePassword,
      });
    } catch (err) {
      setShareError(err instanceof Error ? err.message : 'Failed to generate share link');
    } finally {
      setIsSharing(false);
    }
  }, [traceResult, expirationDays, sharePassword]);

  const handleTrace = useCallback(async () => {
    if (!code.trim()) return;
    setIsLoading(true);
    setError(null);
    reset(); // Reset to beginning
    setTraceResult(null);

    try {
      trackEvent('trace_run_started', {
        code_length: code.length,
        concept_tags: extractConceptTags(code),
      });
      const result = await api.runTrace(code);
      setTraceResult(result);
      if (result.error) {
        setError(result.error_message ?? result.error);
        trackEvent('trace_run_failed', { error: result.error });
      } else {
        trackEvent('trace_run_completed', {
          total_steps: result.total_steps,
          duration_ms: result.duration_ms,
        });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to run trace';
      setError(msg);
      trackEvent('trace_run_failed', { error: msg });
    } finally {
      setIsLoading(false);
    }
  }, [code, reset]);

  const handleLineClick = useCallback((lineNumber: number) => {
    setSelectedLine(lineNumber);
    setShowExplanation(false);
    trackEvent('editor_line_clicked', { line_number: lineNumber });
  }, []);

  const handleWhyIsThisHere = useCallback(() => {
    // Enable if we have a selected line OR if we're tracing (currentStepData has a line)
    if (selectedLine !== null || currentStepData?.line_number) {
      const line = selectedLine ?? currentStepData?.line_number ?? 1;
      setShowExplanation(true);
      trackEvent('ai_explanation_requested', {
        line_number: line,
        line_content: code.split('\n')[line - 1] ?? '',
      });
    }
  }, [selectedLine, currentStepData, code]);

  const currentLine = currentStepData?.line_number ?? selectedLine ?? 1;
  const whyButtonDisabled = selectedLine === null && !currentStepData?.line_number;

  return (
    <div className={styles.container}>
      {/* Top bar */}
      <header className={styles.topBar}>
        <div className={styles.brand}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </div>
        {isAuthenticated && (
          <button
            className={styles.dashboardBtn}
            onClick={() => router.push('/dashboard')}
            title="Go to Dashboard"
          >
            Dashboard
          </button>
        )}
        <div className={styles.actions}>
          <ThemeToggle />
          {isAnalyzing && <span className={styles.analyzingBadge}>◈ Analyzing…</span>}
          {!isAnalyzing && annotations.length > 0 && (
            <span className={styles.annotationCount}>
              {annotations.length} {annotations.length === 1 ? 'issue' : 'issues'}
            </span>
          )}
          <button
            className={styles.shareBtn}
            onClick={handleShareClick}
            disabled={!traceResult}
            title={!traceResult ? 'Run the trace first' : 'Share this trace'}
          >
            🔗 Share
          </button>
          <button
            className={styles.saveBtn}
            onClick={handleSaveTrace}
            disabled={!traceResult || isSaving}
            title={!traceResult ? 'Run the trace first' : 'Save this trace'}
          >
            {isSaving ? '⏳ Saving...' : saveSuccess ? '✓ Saved!' : '💾 Save'}
          </button>
          <button
            className={styles.traceBtn}
            onClick={handleTrace}
            disabled={isLoading || !code.trim()}
          >
            {isLoading ? '⏳ Tracing...' : '▶ Trace'}
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className={styles.main}>
        {/* Editor panel */}
        <div className={styles.editorPanel}>
          <EditorErrorBoundary>
            <CodeEditor
              code={code}
              onChange={setCode}
              onLineClick={handleLineClick}
              currentLine={traceResult ? currentLine : undefined}
              annotations={annotations}
            />
          </EditorErrorBoundary>
        </div>

        {/* Right panel */}
        <div className={styles.rightPanel}>
          {/* Variable panel */}
          <div className={styles.variablePanel}>
            <VariablePanelErrorBoundary>
              <VariablePanel
                variables={currentStepData?.variables ?? {}}
                branches={currentStepData?.branches_taken ?? {}}
                isLoading={isLoading}
              />
            </VariablePanelErrorBoundary>
          </div>

          {/* Explanation panel */}
          {showExplanation && (selectedLine !== null || currentStepData?.line_number) && (
            <div className={styles.explanationPanel}>
              <ExplanationPanelErrorBoundary>
                <ExplanationPanel
                  code={code}
                  lineNumber={selectedLine ?? currentStepData?.line_number ?? 1}
                  lineContent={
                    code.split('\n')[(selectedLine ?? currentStepData?.line_number ?? 1) - 1] ?? ''
                  }
                  locals={currentStepData?.variables ?? {}}
                  onClose={() => setShowExplanation(false)}
                />
              </ExplanationPanelErrorBoundary>
            </div>
          )}
        </div>
      </main>

      {/* Bottom controls */}
      {traceResult && steps.length > 0 && (
        <footer className={styles.footer}>
          <AnimationControls
            steps={steps}
            currentStep={currentStep}
            onStepChange={jumpToStep}
            totalSteps={steps.length}
            durationMs={traceResult.duration_ms}
            playbackState={playbackState}
            speed={speed}
            play={() => {
              play();
              trackEvent('trace_playback_started', { current_step: currentStep });
            }}
            pause={() => {
              pause();
              trackEvent('trace_playback_paused', { current_step: currentStep });
            }}
            togglePlayPause={() => {
              togglePlayPause();
              trackEvent('trace_playback_toggled', { current_step: currentStep, state: playbackState });
            }}
            stepForward={() => {
              stepForward();
              trackEvent('trace_step_navigated', { direction: 'forward', current_step: currentStep + 1 });
            }}
            stepBackward={() => {
              stepBackward();
              trackEvent('trace_step_navigated', { direction: 'backward', current_step: currentStep - 1 });
            }}
            jumpToStep={(step) => {
              jumpToStep(step);
              trackEvent('trace_step_jumped', { step });
            }}
            setSpeed={(newSpeed) => {
              setSpeed(newSpeed);
              trackEvent('trace_speed_changed', { speed: newSpeed });
            }}
            reset={() => {
              reset();
              trackEvent('trace_reset');
            }}
          />
          <div className={styles.lineActions}>
            <button
              className={styles.whatIfBtn}
              onClick={() => setShowWhatIf(true)}
              disabled={!traceResult || (traceResult.steps?.length ?? 0) === 0}
              title={!traceResult ? 'Run the trace first' : 'Modify initial values and replay'}
            >
              🔄 What If?
            </button>
            <button
              className={styles.whyBtn}
              onClick={handleWhyIsThisHere}
              disabled={whyButtonDisabled}
              title={
                whyButtonDisabled
                  ? 'Click a line first to select it'
                  : 'Get AI explanation for this line'
              }
            >
              💡 Why is this here?
            </button>
          </div>
        </footer>
      )}

      {/* Share Modal */}
      {showShareModal && (
        <div className={styles.modalOverlay} onClick={() => setShowShareModal(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>Share Trace</h2>

            {!shareResult ? (
              <>
                <div className={styles.modalField}>
                  <label className={styles.modalLabel}>Expiration</label>
                  <select
                    className={styles.modalSelect}
                    value={expirationDays ?? ''}
                    onChange={(e) =>
                      setExpirationDays(e.target.value === '' ? null : Number(e.target.value))
                    }
                  >
                    <option value="">Never expires</option>
                    <option value="1">24 hours</option>
                    <option value="7">7 days</option>
                    <option value="30">30 days</option>
                    <option value="90">90 days</option>
                    <option value="365">1 year</option>
                  </select>
                </div>

                <div className={styles.modalField}>
                  <label className={styles.modalLabel}>Password (optional)</label>
                  <input
                    type="password"
                    className={styles.modalInput}
                    placeholder="Leave blank for no password"
                    value={sharePassword}
                    onChange={(e) => setSharePassword(e.target.value)}
                    maxLength={128}
                  />
                  <span className={styles.modalHint}>
                    Viewers must enter this password to access the trace.
                  </span>
                </div>

                {shareError && <div className={styles.modalError}>{shareError}</div>}

                <div className={styles.modalActions}>
                  <button
                    className={styles.modalCancelBtn}
                    onClick={() => setShowShareModal(false)}
                  >
                    Cancel
                  </button>
                  <button
                    className={styles.modalConfirmBtn}
                    onClick={handleShareSubmit}
                    disabled={isSharing}
                  >
                    {isSharing ? 'Generating...' : 'Generate Link'}
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className={styles.shareLinkBox}>
                  <input
                    type="text"
                    readOnly
                    className={styles.shareLinkInput}
                    value={
                      typeof window !== 'undefined'
                        ? `${window.location.origin}${shareResult.share_url}`
                        : shareResult.share_url
                    }
                    onClick={(e) => (e.target as HTMLInputElement).select()}
                  />
                  <button
                    className={styles.copyBtn}
                    onClick={() => {
                      navigator.clipboard.writeText(
                        typeof window !== 'undefined'
                          ? `${window.location.origin}${shareResult.share_url}`
                          : shareResult.share_url
                      );
                    }}
                  >
                    📋 Copy
                  </button>
                </div>
                {shareResult.has_password && (
                  <p className={styles.shareNote}>🔒 This link is password-protected.</p>
                )}
                {shareResult.expires_at && (
                  <p className={styles.shareNote}>
                    ⏱ Expires: {new Date(shareResult.expires_at).toLocaleDateString()}
                  </p>
                )}
                <div className={styles.modalActions}>
                  <button
                    className={styles.modalCancelBtn}
                    onClick={() => setShowShareModal(false)}
                  >
                    Done
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* WhatIf Modal */}
      {showWhatIf && (
        <WhatIfModal
          steps={traceResult?.steps ?? []}
          code={code}
          isLoading={whatIfLoading}
          onClose={() => setShowWhatIf(false)}
          onSubmit={async (initialNamespace, changedVars) => {
            setShowWhatIf(false);
            setWhatIfLoading(true);
            setTraceResult(null);
            setError(null);
            reset();
            trackEvent('what_if_submitted', {
              changed_variables: Object.keys(initialNamespace),
            });
            try {
              const result = await runTraceApi(code, { initialNamespace });
              if (result.error) {
                setError(result.error_message ?? result.error);
              } else {
                setTraceResult({
                  trace_id: result.trace_id ?? '',
                  steps: result.steps ?? [],
                  total_steps: result.total_steps ?? result.steps?.length ?? 0,
                  duration_ms: result.duration_ms ?? 0,
                });
              }
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Failed to run trace');
            } finally {
              setWhatIfLoading(false);
            }
          }}
        />
      )}

      {/* Error display */}
      {error && (
        <div className={styles.errorBanner}>
          <span className={styles.errorIcon}>⚠</span>
          <span className={styles.errorMessage}>{error}</span>
          <button className={styles.errorDismiss} onClick={() => setError(null)}>
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
