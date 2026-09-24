/**
 * useTraceRunner — owns the "Run trace" execution state.
 *
 * Every call to `run()` fires the network request, resets the player to step 0,
 * and stores the result. The hook isolates:
 *   - `isLoading` flag the page renders as a spinner
 *   - `error` flag the page displays at the top
 *   - `result` (TraceResult) that feeds the rest of the UI
 *   - the matching `originalResult` used by What-If/compare mode
 *   - `compareMode` toggle that What-If sets/clears
 *
 * This consolidates the dispatch + retry logic the page used to inline.
 *
 * The hook depends only on `api.runTrace` and `extractConceptTags`. The latter
 * is injected so the page can keep ownership of the extractor definition.
 */

import { useCallback, useRef, useState } from 'react';
import { api } from '@/lib/api';
import { trackEvent } from '@/lib/analytics';
import type { TraceResult } from '@/types/trace';

export interface UseTraceRunnerOptions {
  /** Reset the playback animation to step 0 before storing the new result. */
  onBeforeRun?: () => void;
  /** Extract concept tags from the current code. Required to log analytics. */
  extractConceptTags: (code: string) => string[];
}

export interface UseTraceRunnerReturn {
  result: TraceResult | null;
  originalResult: TraceResult | null;
  compareMode: boolean;
  isLoading: boolean;
  error: string | null;
  run: (code: string) => Promise<void>;
  setOriginalResult: (next: TraceResult | null) => void;
  setCompareMode: (next: boolean) => void;
  /**
   * Low-level override for the result. Used by the What-If modal which runs
   * its own trace with custom initial variables.
   */
  setResult: (next: TraceResult | null) => void;
}

export function useTraceRunner({
  onBeforeRun,
  extractConceptTags,
}: UseTraceRunnerOptions): UseTraceRunnerReturn {
  const [result, setResult] = useState<TraceResult | null>(null);
  const [originalResult, setOriginalResult] = useState<TraceResult | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Keep the latest `onBeforeRun` in a ref so the callback below has a stable
  // identity (avoids re-running effects that depend on `run`).
  const onBeforeRunRef = useRef(onBeforeRun);
  onBeforeRunRef.current = onBeforeRun;

  const run = useCallback(
    async (code: string) => {
      if (!code.trim()) return;
      setIsLoading(true);
      setError(null);

      // Reset the animation to step 0 before the new result lands
      onBeforeRunRef.current?.();

      setResult(null);

      try {
        trackEvent('trace_run_started', {
          code_length: code.length,
          concept_tags: extractConceptTags(code),
        });
        const next = await api.runTrace(code);
        setResult(next);
        setOriginalResult(next);
        setCompareMode(false);
        if (next.error) {
          setError(next.error_message ?? next.error);
          trackEvent('trace_run_failed', { error: next.error });
        } else {
          trackEvent('trace_run_completed', {
            total_steps: next.total_steps,
            duration_ms: next.duration_ms,
          });
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to run trace';
        setError(msg);
        trackEvent('trace_run_failed', { error: msg });
      } finally {
        setIsLoading(false);
      }
    },
    [extractConceptTags],
  );

  return {
    result,
    originalResult,
    compareMode,
    isLoading,
    error,
    run,
    setOriginalResult,
    setCompareMode,
    setResult,
  };
}
