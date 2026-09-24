'use client';
/**
 * Purpose: The main trace editor — code input, run, explanation streaming, share modal.
 * Collaborators: —
 * Last significant change: Workstream 9
 */


import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { runTrace as runTraceApi } from '@/lib/api';
import { trackEvent } from '@/lib/analytics';
import { useTrace } from '@/hooks/useTrace';
import { useAuth } from '@/hooks/useAuth';
import { useShareTrace } from '@/hooks/useShareTrace';
import { useSaveTrace } from '@/hooks/useSaveTrace';
import { useCodeAnalysis } from '@/hooks/useCodeAnalysis';
import { useTraceRunner } from '@/hooks/useTraceRunner';
import { VariablePanel } from '@/components/tracer/VariablePanel';
import { AnimationControls } from '@/components/tracer/AnimationControls';
import { ExplanationPanel } from '@/components/llm/ExplanationPanel';
import { WhatIfModal } from '@/components/tracer/WhatIfModal';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { TraceTreePanel } from '@/components/tracer/TraceTreePanel';
import { TutorChallenge } from '@/components/tracer/TutorChallenge';
import { LoadDial } from '@/components/tracer/LoadDial';
import { useTraceLoad } from '@/hooks/useTraceLoad';
import { trackLoadEvent } from '@/lib/analytics';
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

/* T1-A: tiny wrapper that pairs `useTraceLoad` + `LoadDial`. We define
 * it here (rather than inline) so the JSX above stays readable.
 */
function LoadDialWrapper({ traceId }: { traceId: string }) {
  const { data, loading, error } = useTraceLoad({ traceId });
  return <LoadDial load={data} loading={loading} error={error} />;
}

export default function TracerPage() {
  const router = useRouter();
  const [code, setCode] = useState(SAMPLE_CODE);
  const [error, setError] = useState<string | null>(null);
  const [selectedLine, setSelectedLine] = useState<number | null>(null);
  const [showExplanation, setShowExplanation] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Static analysis: debounced re-run of api.analyzeCode on code change.
  const { annotations, isAnalyzing } = useCodeAnalysis(code);

  // ── Trace execution (replaces ~30 lines of state + handleTrace) ─────
  // The runner does its own pre-run housekeeping (clears result, fires
  // analytics). The animation player is reset from the JSX `onClick` so
  // we don't need to thread `reset` through here.
  const {
    result: traceResult,
    originalResult: originalTraceResult,
    compareMode,
    isLoading,
    error: traceError,
    run: runTrace,
    setOriginalResult: setOriginalTraceResult,
    setCompareMode,
    setResult: setTraceResult,
  } = useTraceRunner({
    extractConceptTags,
  });

  // useTrace hook — owns the animation player. Declared AFTER useTraceRunner
  // so it can read `traceResult.steps` synchronously below.
  const steps = traceResult?.steps ?? [];

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

  // ── Share modal state + submit (replaces 9 useState calls + 2 handlers)
  const {
    isOpen: showShareModal,
    open: openShareModal,
    close: closeShareModal,
    password: sharePassword,
    setPassword: setSharePassword,
    expirationDays,
    setExpirationDays,
    isSharing,
    error: shareError,
    result: shareResult,
    submit: submitShare,
  } = useShareTrace();

  // ── Save-state + handler (replaces 3 useState + handleSaveTrace)
  const {
    isSaving,
    saveSuccess,
    error: saveError,
    save: handleSaveTrace,
  } = useSaveTrace({
    requireLogin: () => router.push('/auth/login'),
  });

  // ── What-If modal state
  const [showWhatIf, setShowWhatIf] = useState(false);
  const [whatIfLoading, setWhatIfLoading] = useState(false);

  // ── Execution tree panel state
  const [showTreePanel, setShowTreePanel] = useState(true);

  // Wrap runner so the JSX button can `onClick={handleTrace}` and reset the
  // animation player at the same time. (`runTrace` alone doesn't know about
  // the player.)
  const handleTrace = useCallback(async () => {
    reset();
    await runTrace(code);
  }, [reset, runTrace, code]);

  const [completedCheckpoints, setCompletedCheckpoints] = useState<Set<number>>(new Set());

  const checkpoints = traceResult?.checkpoints ?? [];
  const activeCheckpoint = checkpoints.find(
    (cp) => cp.step_number === currentStep && !completedCheckpoints.has(currentStep)
  );

  // Auto-pause when reaching an uncompleted checkpoint step during playback
  useEffect(() => {
    if (activeCheckpoint && playbackState === 'playing') {
      pause();
    }
  }, [activeCheckpoint, playbackState, pause]);

  const handleSelectStep = useCallback(
    (stepIdx: number) => {
      jumpToStep(stepIdx);
      if (playbackState === 'playing') {
        pause();
      }
    },
    [jumpToStep, playbackState, pause]
  );

  // ── Authentication state ───────────────────────────────────────────
  const { isAuthenticated: isAuthFromHook } = useAuth();
  // Sync with local state so the rest of the component doesn't change
  useEffect(() => {
    setIsAuthenticated(isAuthFromHook);
  }, [isAuthFromHook]);

  // ── Track session time-on-task ───────────────────────────────────
  useEffect(() => {
    trackEvent('tracer_session_started');
    const startTime = Date.now();
    return () => {
      const durationSeconds = (Date.now() - startTime) / 1000;
      trackEvent('tracer_session_ended', { duration_seconds: durationSeconds });
    };
  }, []);

  // ── T1-A: emit load-bearing pause events ─────────────────────────
  // When the user dwells on a line (selectedLine is stable for ≥2s)
  // we emit a `tracer_pause` event. `selectedLine === null` flushes the
  // pending pause. We only fire on the *latest* settled line so the
  // server doesn't see one event per re-render.
  useEffect(() => {
    const traceId = traceResult?.trace_id;
    if (!traceId) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    if (selectedLine !== null) {
      timer = setTimeout(() => {
        trackLoadEvent('tracer_pause', {
          trace_id: traceId,
          line: selectedLine,
          duration_ms: 2000,
        });
      }, 2000);
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [selectedLine, traceResult?.trace_id]);

  // ── Combine error sources ─────────────────────────────────────────
  useEffect(() => {
    if (traceError) {
      setError(traceError);
    }
  }, [traceError]);
  useEffect(() => {
    if (saveError) {
      setError(saveError);
    }
  }, [saveError]);

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
          <span className={styles.brandName}>CogniTrace</span>
        </div>
        <button
          className={styles.dashboardBtn}
          onClick={() => router.push(isAuthenticated ? '/dashboard' : '/auth/login')}
          title={isAuthenticated ? 'Go to Dashboard' : 'Go to Login'}
        >
          {isAuthenticated ? 'Dashboard' : 'Login'}
        </button>
        <div className={styles.actions}>
          {traceResult && (
            <button
              className={styles.outlineToggleBtn}
              onClick={() => setShowTreePanel((prev) => !prev)}
              title="Toggle Execution Outline"
            >
              {showTreePanel ? '📂 Hide Outline' : '📂 Show Outline'}
            </button>
          )}
          <ThemeToggle />
          {isAnalyzing && <span className={styles.analyzingBadge}>◈ Analyzing…</span>}
          {!isAnalyzing && annotations.length > 0 && (
            <span className={styles.annotationCount}>
              {annotations.length} {annotations.length === 1 ? 'issue' : 'issues'}
            </span>
          )}
          <button
            className={styles.shareBtn}
            onClick={openShareModal}
            disabled={!traceResult}
            title={!traceResult ? 'Run the trace first' : 'Share this trace'}
          >
            🔗 Share
          </button>
          <button
            className={styles.saveBtn}
            onClick={() => {
              if (traceResult) {
                void handleSaveTrace(traceResult, code, extractConceptTags(code));
              }
            }}
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
              compareLine={compareMode && originalTraceResult ? (originalTraceResult.steps[Math.min(currentStep, originalTraceResult.steps.length - 1)]?.line_number) : undefined}
              annotations={annotations}
            />
          </EditorErrorBoundary>
        </div>

        {/* Right panel */}
        <div className={styles.rightPanel}>
          {compareMode && originalTraceResult ? (
            <div className={styles.compareGrid}>
              <div className={styles.compareCol}>
                <h4 className={styles.compareColHeader}>⏮ Original Trace</h4>
                <VariablePanel
                  variables={originalTraceResult.steps[Math.min(currentStep, originalTraceResult.steps.length - 1)]?.variables ?? {}}
                  branches={originalTraceResult.steps[Math.min(currentStep, originalTraceResult.steps.length - 1)]?.branches_taken ?? {}}
                  isLoading={isLoading}
                />
              </div>
              <div className={styles.compareCol}>
                <h4 className={styles.compareColHeader}>🔁 Modified Trace</h4>
                <VariablePanel
                  variables={currentStepData?.variables ?? {}}
                  branches={currentStepData?.branches_taken ?? {}}
                  isLoading={isLoading}
                />
              </div>
            </div>
          ) : (
            <>
              {/* Variable panel */}
              <div className={styles.variablePanel}>
                <VariablePanelErrorBoundary>
                  {activeCheckpoint ? (
                    <TutorChallenge
                      checkpoint={activeCheckpoint}
                      code={code}
                      steps={steps}
                      traceId={traceResult?.trace_id}
                      // T1-C: forward the trace's primary concept tag so the
                      // adaptive selector can pick a difficulty mode. We compute
                      // the same tag list we save with — `extractConceptTags`
                      // runs locally, no LLM.
                      conceptTag={extractConceptTags(code)[0] ?? null}
                      onSuccess={() => setCompletedCheckpoints(prev => {
                        const next = new Set(prev);
                        next.add(currentStep);
                        return next;
                      })}
                    />
                  ) : (
                    <VariablePanel
                      variables={currentStepData?.variables ?? {}}
                      branches={currentStepData?.branches_taken ?? {}}
                      isLoading={isLoading}
                    />
                  )}
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

              {/* T1-A: Cognitive Load Dashboard dial.
                  Hidden until the trace is saved; otherwise there is no
                  signal to aggregate. */}
              {traceResult?.trace_id && (
                <div className={styles.loadPanel}>
                  <h4 className={styles.compareColHeader}>📊 Cognitive Load</h4>
                  <LoadDialWrapper traceId={traceResult.trace_id} />
                </div>
              )}
            </>
          )}
        </div>

        {/* Trace outline tree explorer */}
        {traceResult && showTreePanel && (
          <TraceTreePanel
            steps={steps}
            currentStep={currentStep}
            onSelectStep={handleSelectStep}
            code={code}
          />
        )}
      </main>

      {/* Bottom controls */}
      {traceResult && steps.length > 0 && (
        <footer className={styles.footer}>
          {!activeCheckpoint ? (
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
          ) : (
            <div style={{ width: '100%', padding: '1rem', textAlign: 'center', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', fontWeight: 600, borderTop: '1px solid rgba(239, 68, 68, 0.2)' }}>
              🔒 Timeline locked by AI Tutor. Please answer the challenge question on the right to resume.
            </div>
          )}
          <div className={styles.lineActions}>
            {compareMode ? (
              <button
                className={styles.exitCompareBtn}
                onClick={() => {
                  setCompareMode(false);
                  setTraceResult(originalTraceResult);
                }}
              >
                ✕ Exit Compare
              </button>
            ) : (
              <button
                className={styles.whatIfBtn}
                onClick={() => {
                  // T1-A: emit a load-bearing replay event so the cognitive
                  // load dashboard counts replays as interaction pressure.
                  if (traceResult?.trace_id) {
                    trackLoadEvent('tracer_whatif_replay', {
                      trace_id: traceResult.trace_id,
                    });
                  }
                  setShowWhatIf(true);
                }}
                disabled={!traceResult || (traceResult.steps?.length ?? 0) === 0}
                title={!traceResult ? 'Run the trace first' : 'Modify initial values and replay'}
              >
                🔄 What If?
              </button>
            )}
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
        <div className={styles.modalOverlay} onClick={closeShareModal}>
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
                    onClick={closeShareModal}
                  >
                    Cancel
                  </button>
                  <button
                    className={styles.modalConfirmBtn}
                    onClick={() => {
                      if (traceResult?.trace_id) {
                        void submitShare(traceResult.trace_id);
                      }
                    }}
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
                    onClick={closeShareModal}
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
                setCompareMode(true);
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
