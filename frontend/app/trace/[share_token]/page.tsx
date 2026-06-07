// frontend/app/trace/[share_token]/page.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { fetchSharedTrace, saveTrace, authFetch } from '@/lib/api';
import { getSupabase } from '@/lib/supabase';
import type { SharedTraceData } from '@/types/user';
import type { TraceResult } from '@/types/trace';
import { VariablePanel } from '@/components/tracer/VariablePanel';
import { AnimationControls } from '@/components/tracer/AnimationControls';
import { useTrace } from '@/hooks/useTrace';
import styles from './share.module.css';

const CodeEditor = dynamic(() => import('@/components/editor/CodeEditor').then(m => m.CodeEditor), {
  ssr: false,
  loading: () => <div className={styles.editorLoading}>Loading editor...</div>,
});

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000') + '/api';
function getApiBase() {
  return API_BASE;
}

export default function SharedTracePage() {
  const params = useParams();
  const router = useRouter();
  const shareToken = params.share_token as string;

  const [trace, setTrace] = useState<SharedTraceData | null>(null);
  const [code, setCode] = useState('');
  const [traceResult, setTraceResult] = useState<TraceResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [password, setPassword] = useState('');
  const [passwordRequired, setPasswordRequired] = useState(false);
  const [expired, setExpired] = useState(false);
  const [isForking, setIsForking] = useState(false);

  const steps = traceResult?.steps ?? [];

  // Use useTrace hook for animation state management - must be before any callbacks that use it
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

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchSharedTrace(shareToken);
        setTrace(data);
        setCode(data.code);
        if (data.steps?.length) {
          setTraceResult({
            trace_id: data.id,
            steps: data.steps,
            total_steps: data.steps.length,
            duration_ms: 0,
          });
        }
      } catch (err) {
        const errObj = err as Error & { status?: number; body?: Record<string, unknown> };
        if (errObj.message === 'TRACE_NOT_FOUND') {
          setNotFound(true);
        } else if (errObj.status === 401) {
          const body = errObj.body as Record<string, unknown>;
          if (body?.error === 'PASSWORD_REQUIRED') {
            setPasswordRequired(true);
          } else {
            setError('Incorrect password');
          }
        } else if (errObj.status === 410) {
          setExpired(true);
        } else {
          setError(err instanceof Error ? err.message : 'Failed to load trace');
        }
      }
    }
    load();
  }, [shareToken]);

  // Password submission for protected traces
  const handlePasswordSubmit = useCallback(async () => {
    try {
      const data = await fetchSharedTrace(shareToken);
      setTrace(data);
      setCode(data.code);
      setPasswordRequired(false);
      if (data.steps?.length) {
        setTraceResult({
          trace_id: data.id,
          steps: data.steps,
          total_steps: data.steps.length,
          duration_ms: 0,
        });
      }
    } catch (err) {
      const errObj = err as Error & { status?: number };
      if (errObj.status === 401) {
        setError('Incorrect password');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load trace');
      }
    }
  }, [shareToken]);

  // Fork handler
  const handleFork = useCallback(async () => {
    setIsForking(true);
    setError(null);
    try {
      const res = await authFetch(
        `${getApiBase()}/traces/shared/${shareToken}/fork`,
        { method: 'POST' }
      );
      if (!res.ok) throw new Error('Fork failed');
      const data = await res.json();
      router.push(data.share_url);
    } catch {
      router.push('/auth/login');
    } finally {
      setIsForking(false);
    }
  }, [shareToken, router]);

  // Update document title when trace loads
  useEffect(() => {
    if (!trace) return;
    const firstLine = trace.code.split('\n')[0];
    document.title = `CogniTrace Trace — ${firstLine ? firstLine.slice(0, 60) : ''}`;
  }, [trace]);

  const handleTrace = useCallback(async () => {
    if (!code.trim()) return;
    setIsLoading(true);
    setError(null);
    jumpToStep(0);
    try {
      const { runTrace } = await import('@/lib/api');
      const result = await runTrace(code);
      setTraceResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run trace');
    } finally {
      setIsLoading(false);
    }
  }, [code, jumpToStep]);

  const handleSave = useCallback(async () => {
    const { data } = await getSupabase().auth.getSession();
    if (!data?.session) {
      router.push('/auth/login');
      return;
    }
    if (!traceResult?.steps?.length) {
      setError('Run the trace first before saving.');
      return;
    }
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
      if (err instanceof Error && err.message === 'AUTH_REQUIRED') {
        router.push('/auth/login');
        return;
      }
      setError(err instanceof Error ? err.message : 'Failed to save trace');
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
          <Link href="/" className={styles.homeLink}>
            ← Go to CogniTrace
          </Link>
        </div>
      </div>
    );
  }

  if (expired) {
    return (
      <div className={styles.page}>
        <div className={styles.notFound}>
          <h1>🔗 This trace link has expired</h1>
          <p>Sign in to CogniTrace to view this trace.</p>
          <Link href="/auth/login" className={styles.homeLink}>
            ← Sign in to CogniTrace
          </Link>
        </div>
      </div>
    );
  }

  if (passwordRequired) {
    return (
      <div className={styles.page}>
        <div className={styles.passwordGate}>
          <h1>🔒 Password Required</h1>
          <p>Enter the password to view this trace.</p>
          <input
            type="password"
            className={styles.passwordInput}
            placeholder="Enter password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handlePasswordSubmit()}
            autoFocus
          />
          {error && <p className={styles.passwordError}>{error}</p>}
          <button className={styles.passwordSubmitBtn} onClick={handlePasswordSubmit}>
            View Trace
          </button>
          <Link href="/" className={styles.homeLink}>
            ← Go to CogniTrace
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Link href="/" className={styles.brand}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CogniTrace</span>
        </Link>
        <div className={styles.actions}>
          <button
            onClick={handleFork}
            disabled={isForking}
            className={styles.forkBtn}
            title="Fork this trace to your account"
          >
            {isForking ? '⏳' : '🍴'} Fork & Trace
          </button>
          <button
            onClick={handleSave}
            disabled={!traceResult || isSaving}
            className={styles.saveBtn}
          >
            {isSaving ? '⏳ Saving...' : saveSuccess ? '✓ Saved!' : '💾 Save'}
          </button>
          <button
            onClick={handleTrace}
            disabled={isLoading || !code.trim()}
            className={styles.traceBtn}
          >
            {isLoading ? '⏳' : '▶'} Trace
          </button>
        </div>
      </header>

      {error && (
        <div className={styles.errorBanner}>
          <span>⚠</span> {error}
          <button onClick={() => setError(null)} className={styles.dismissBtn}>
            ✕
          </button>
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
            steps={steps}
            currentStep={currentStep}
            onStepChange={(step) => jumpToStep(step)}
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
        </footer>
      )}
    </div>
  );
}
