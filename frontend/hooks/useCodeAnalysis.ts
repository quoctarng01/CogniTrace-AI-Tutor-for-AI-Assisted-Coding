/**
 * useCodeAnalysis — debounced static analysis hook.
 *
 * Runs a debounced call to `api.analyzeCode` whenever `code` changes and
 * returns the `annotations` plus an `isAnalyzing` flag. Replaces ~25 lines
 * of state, ref, effect, and cleanup duplicated in the tracer page.
 *
 * Timing: 600ms debounce. This matches the visual cadence of typing — the
 * annotations panel only re-renders after the user pauses.
 *
 * Edge case: empty code clears annotations immediately instead of firing
 * the API (which would 400 anyway).
 */

import { useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import type { Annotation } from '@/types/annotation';

const DEBOUNCE_MS = 600;

export interface UseCodeAnalysisReturn {
  annotations: Annotation[];
  isAnalyzing: boolean;
}

export function useCodeAnalysis(code: string): UseCodeAnalysisReturn {
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Clear any pending timer so a new keystroke doesn't double-fire
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (!code.trim()) {
      // Nothing to analyze — reset without a server round-trip
      setAnnotations([]);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setIsAnalyzing(true);
      try {
        const result = await api.analyzeCode(code);
        setAnnotations(result.annotations);
      } catch {
        // Non-critical: clear stale annotations rather than surfacing the error
        setAnnotations([]);
      } finally {
        setIsAnalyzing(false);
      }
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [code]);

  return { annotations, isAnalyzing };
}
