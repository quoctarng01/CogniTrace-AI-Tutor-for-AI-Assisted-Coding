/**
 * useSaveTrace — save-to-tray state and handler.
 *
 * Saves the current trace (code + steps + concept tags) to the user's tray.
 *
 * Returns:
 *   - `isSaving`, `saveSuccess`, `error` flags the caller renders
 *   - `save(traceResult)` triggers the save
 *   - A redirect is performed via the injected `requireLogin` callback when
 *     the user is not authenticated, so the hook stays decoupled from
 *     the router.
 *
 * The hook itself does NOT track the concept-tag extractor — that lives in the
 * page so different callers can compute it differently.
 */

import { useCallback, useState } from 'react';
import { saveTrace } from '@/lib/api';
import { getSupabase } from '@/lib/supabase';
import { trackEvent } from '@/lib/analytics';
import type { TraceResult } from '@/types/trace';

export interface UseSaveTraceOptions {
  /** Invoked when an unauthenticated user tries to save. */
  requireLogin: () => void;
}

export interface UseSaveTraceReturn {
  isSaving: boolean;
  saveSuccess: boolean;
  error: string | null;
  save: (traceResult: TraceResult, code: string, conceptTags: string[]) => Promise<void>;
  /** Clear the "saved successfully" banner before its 3s timeout fires. */
  dismissSuccess: () => void;
}

export function useSaveTrace({ requireLogin }: UseSaveTraceOptions): UseSaveTraceReturn {
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = useCallback(
    async (traceResult: TraceResult, code: string, conceptTags: string[]) => {
      if (!traceResult?.steps?.length) return;
      const { data } = await getSupabase().auth.getSession();
      if (!data?.session) {
        requireLogin();
        return;
      }
      setIsSaving(true);
      setError(null);
      setSaveSuccess(false);
      try {
        await saveTrace({ code, steps: traceResult.steps, concept_tags: conceptTags });
        setSaveSuccess(true);
        trackEvent('trace_saved', {
          concept_tags: conceptTags,
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
    },
    [requireLogin],
  );

  const dismissSuccess = useCallback(() => setSaveSuccess(false), []);

  return {
    isSaving,
    saveSuccess,
    error,
    save,
    dismissSuccess,
  };
}
