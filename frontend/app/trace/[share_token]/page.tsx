// frontend/app/trace/[share_token]/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { fetchSharedTrace, saveTrace } from "@/lib/api";
import { getSupabase } from "@/lib/supabase";
import type { SharedTraceData } from "@/types/user";
import type { TraceResult } from "@/types/trace";
import { VariablePanel } from "@/components/tracer/VariablePanel";
import { AnimationControls } from "@/components/tracer/AnimationControls";
import styles from "./share.module.css";

const CodeEditor = dynamic(
  () => import("@/components/editor/CodeEditor").then((m) => m.CodeEditor),
  { ssr: false, loading: () => <div className={styles.editorLoading}>Loading editor...</div> }
);

export default function SharedTracePage() {
  const params = useParams();
  const router = useRouter();
  const shareToken = params.share_token as string;

  const [trace, setTrace] = useState<SharedTraceData | null>(null);
  const [code, setCode] = useState("");
  const [traceResult, setTraceResult] = useState<TraceResult | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchSharedTrace(shareToken);
        setTrace(data);
        setCode(data.code);
        if (data.steps?.length) {
          setTraceResult({ trace_id: data.id, steps: data.steps, total_steps: data.steps.length, duration_ms: 0 });
        }
      } catch (err) {
        if (err instanceof Error && err.message === "TRACE_NOT_FOUND") setNotFound(true);
        else setError(err instanceof Error ? err.message : "Failed to load trace");
      }
    }
    load();
  }, [shareToken]);

  const handleTrace = useCallback(async () => {
    if (!code.trim()) return;
    setIsLoading(true);
    setError(null);
    setCurrentStep(0);
    try {
      const { runTrace } = await import("@/lib/api");
      const result = await runTrace(code);
      setTraceResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run trace");
    } finally {
      setIsLoading(false);
    }
  }, [code]);

  const handleSave = useCallback(async () => {
    const { data } = await getSupabase().auth.getSession();
    if (!data?.session) { router.push("/auth/login"); return; }
    if (!traceResult?.steps?.length) { setError("Run the trace first before saving."); return; }
    setIsSaving(true);
    setError(null);
    setSaveSuccess(false);
    try {
      await saveTrace({
        code,
        steps: traceResult.steps,
        concept_tags: trace?.concept_tags ?? [],
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      if (err instanceof Error && err.message === "AUTH_REQUIRED") { router.push("/auth/login"); return; }
      setError(err instanceof Error ? err.message : "Failed to save trace");
    } finally {
      setIsSaving(false);
    }
  }, [code, traceResult, trace, router]);

  if (notFound) {
    return (
      <div className={styles.page}>
        <div className={styles.notFound}>
          <h1>Trace not found</h1>
          <p>This shared trace may have been deleted or the link is invalid.</p>
          <Link href="/" className={styles.homeLink}>← Go to CodeScope</Link>
        </div>
      </div>
    );
  }

  const steps = traceResult?.steps ?? [];
  const currentStepData = steps[currentStep] ?? null;

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Link href="/" className={styles.brand}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </Link>
        <div className={styles.actions}>
          <button onClick={handleSave} disabled={!traceResult || isSaving} className={styles.saveBtn}>
            {isSaving ? "⏳ Saving..." : saveSuccess ? "✓ Saved!" : "💾 Save"}
          </button>
          <button onClick={handleTrace} disabled={isLoading || !code.trim()} className={styles.traceBtn}>
            {isLoading ? "⏳" : "▶"} Trace
          </button>
        </div>
      </header>

      {error && (
        <div className={styles.errorBanner}>
          <span>⚠</span> {error}
          <button onClick={() => setError(null)} className={styles.dismissBtn}>✕</button>
        </div>
      )}

      <main className={styles.main}>
        <div className={styles.editorPanel}>
          <CodeEditor
            code={code}
            onChange={setCode}
            currentLine={traceResult ? currentStepData?.line_number : undefined}
          />
        </div>
        <div className={styles.rightPanel}>
          <VariablePanel
            variables={currentStepData?.variables ?? {}}
            branches={currentStepData?.branches_taken ?? {}}
            isLoading={isLoading}
          />
        </div>
      </main>

      {traceResult && steps.length > 0 && (
        <footer className={styles.footer}>
          <AnimationControls
            steps={steps} currentStep={currentStep} onStepChange={setCurrentStep}
            totalSteps={steps.length} durationMs={traceResult.duration_ms}
          />
        </footer>
      )}
    </div>
  );
}
