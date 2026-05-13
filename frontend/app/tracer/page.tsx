"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { api, saveTrace } from "@/lib/api";
import { getSupabase, getAuthToken } from "@/lib/supabase";
import type { TraceResult, TraceStep } from "@/types/trace";
import type { Annotation } from "@/types/annotation";
import { useTrace } from "@/hooks/useTrace";
import { VariablePanel } from "@/components/tracer/VariablePanel";
import { AnimationControls } from "@/components/tracer/AnimationControls";
import { ExplanationPanel } from "@/components/llm/ExplanationPanel";
import { EditorErrorBoundary, VariablePanelErrorBoundary, ExplanationPanelErrorBoundary } from "@/components/errors/ErrorBoundary";
import styles from "./page.module.css";

// Dynamic imports for client-side only components
const CodeEditor = dynamic(
  () => import("@/components/editor/CodeEditor").then((m) => m.CodeEditor),
  { ssr: false, loading: () => <div className={styles.editorLoading}>Loading editor...</div> }
);

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
  if (/def\s+\w+\(/.test(code)) tags.push("FUNCTION");
  if (/for\s/.test(code)) tags.push("LOOP");
  if (/while\s/.test(code)) tags.push("LOOP");
  if (/if\s/.test(code)) tags.push("CONDITIONAL");
  if (/class\s/.test(code)) tags.push("CLASS");
  if (/try\s|except\s/.test(code)) tags.push("EXCEPTION");
  if (/lambda\s/.test(code)) tags.push("LAMBDA");
  if (/\[.*for.*in.*\]/.test(code)) tags.push("COMPREHENSION");
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

  const steps = traceResult?.steps ?? [];

  // FIX-MD-07: useTrace hook called in parent, not in AnimationControls
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
    if (!data?.session) { router.push("/auth/login"); return; }
    setIsSaving(true);
    setError(null);
    setSaveSuccess(false);
    try {
      await saveTrace({ code, steps: traceResult.steps, concept_tags: extractConceptTags(code) });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      if (err instanceof Error && err.message.includes("UPGRADE_REQUIRED")) {
        setError("Free plan limit reached. Upgrade to Pro to save more traces.");
      } else {
        setError(err instanceof Error ? err.message : "Failed to save");
      }
    } finally {
      setIsSaving(false);
    }
  }, [code, traceResult, router]);

  const handleTrace = useCallback(async () => {
    if (!code.trim()) return;
    setIsLoading(true);
    setError(null);
    reset();  // Reset to beginning
    setTraceResult(null);

    try {
      const result = await api.runTrace(code);
      setTraceResult(result);
      if (result.error) {
        setError(result.error_message ?? result.error);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to run trace";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [code, reset]);

  const handleLineClick = useCallback((lineNumber: number) => {
    setSelectedLine(lineNumber);
    setShowExplanation(false);
  }, []);

  const handleWhyIsThisHere = useCallback(() => {
    // Enable if we have a selected line OR if we're tracing (currentStepData has a line)
    if (selectedLine !== null || currentStepData?.line_number) {
      setShowExplanation(true);
    }
  }, [selectedLine, currentStepData]);

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
            onClick={() => router.push("/dashboard")}
            title="Go to Dashboard"
          >
            Dashboard
          </button>
        )}
        <div className={styles.actions}>
          {isAnalyzing && (
            <span className={styles.analyzingBadge}>◈ Analyzing…</span>
          )}
          {!isAnalyzing && annotations.length > 0 && (
            <span className={styles.annotationCount}>
              {annotations.length} {annotations.length === 1 ? "issue" : "issues"}
            </span>
          )}
          <button
            className={styles.saveBtn}
            onClick={handleSaveTrace}
            disabled={!traceResult || isSaving}
            title={!traceResult ? "Run the trace first" : "Save this trace"}
          >
            {isSaving ? "⏳ Saving..." : saveSuccess ? "✓ Saved!" : "💾 Save"}
          </button>
          <button
            className={styles.traceBtn}
            onClick={handleTrace}
            disabled={isLoading || !code.trim()}
          >
            {isLoading ? "⏳ Tracing..." : "▶ Trace"}
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
                  lineContent={code.split("\n")[(selectedLine ?? currentStepData?.line_number ?? 1) - 1] ?? ""}
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
            play={play}
            pause={pause}
            togglePlayPause={togglePlayPause}
            stepForward={stepForward}
            stepBackward={stepBackward}
            jumpToStep={jumpToStep}
            setSpeed={setSpeed}
            reset={reset}
          />
          <div className={styles.lineActions}>
            <button
              className={styles.whyBtn}
              onClick={handleWhyIsThisHere}
              disabled={whyButtonDisabled}
              title={whyButtonDisabled ? "Click a line first to select it" : "Get AI explanation for this line"}
            >
              💡 Why is this here?
            </button>
          </div>
        </footer>
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
