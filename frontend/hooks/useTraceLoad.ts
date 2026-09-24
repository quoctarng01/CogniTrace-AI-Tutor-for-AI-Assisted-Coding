/**
 * Purpose: Hook for fetching the cognitive-load estimate for a given trace.
 *          Used by `LoadDial` on the tracer page and the trace-detail page.
 * Collaborators: backend/app/routers/load.py (GET /api/load/trace/{trace_id})
 * Last significant change: T1-A (Cognitive Load Dashboard)
 */
'use client';

import { useCallback, useEffect, useState } from 'react';
import { fetchTraceLoad } from '@/lib/api';
import type { LoadResponse } from '@/lib/api';

interface UseTraceLoadArgs {
  traceId: string | null | undefined;
  /** When false, the hook doesn't fetch. Defaults to true. */
  enabled?: boolean;
}

interface UseTraceLoadResult {
  data: LoadResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/**
 * Fetch and cache a trace's cognitive-load estimate.
 *
 * The hook lazily fetches on mount and re-fetches when the traceId
 * changes. It deliberately exposes no auto-refresh — load estimates
 * are not real-time, and forcing the user to wait for a spinner each
 * time would erode trust in the dial.
 */
export function useTraceLoad({
  traceId,
  enabled = true,
}: UseTraceLoadArgs): UseTraceLoadResult {
  const [data, setData] = useState<LoadResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!traceId || !enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchTraceLoad(traceId);
      setData(res);
      if (!res) {
        // 404 — distinguishes from "no signal yet"
        setError('No load signal yet — finish the trace first.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch load');
    } finally {
      setLoading(false);
    }
  }, [traceId, enabled]);

  useEffect(() => {
    void load();
  }, [load]);

  return {
    data,
    loading,
    error,
    refresh: load,
  };
}
