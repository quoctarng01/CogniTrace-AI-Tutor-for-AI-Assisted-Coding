'use client';
/**
 * Purpose: Parallel-fetch the fingerprint-diff response for two inputs
 *          (share tokens or trace ids). Caches by the `(a, b)` pair so
 *          re-renders don't refetch. Used by the /tracer/compare page
 *          (THESIS-05 §4 — T1-D "Fingerprint Comparison / Trace Diff").
 *
 *          Returns `null` while loading and on a soft 404 — the page
 *          decides whether to render the empty state.
 * Collaborators: lib/api.fetchFingerprintDiff
 * Last significant change: T1-D (Trace Diff)
 */
import { useEffect, useState } from 'react';
import { fetchFingerprintDiff } from '@/lib/api';
import type { FingerprintDiffResponse } from '@/types/fingerprint';

interface UseFingerprintDiffArgs {
  a: string | null | undefined;
  b: string | null | undefined;
}

interface UseFingerprintDiffResult {
  data: FingerprintDiffResponse | null;
  isLoading: boolean;
  error: 'not-found' | 'network' | null;
}

// Module-level cache — keyed by sorted (a, b) so `diff(A, B)` and
// `diff(B, A)` share the same entry. Multiple components mounting at
// once fan out one wire request.
const cache = new Map<string, Promise<FingerprintDiffResponse | null>>();

function diffKey(a: string, b: string): string {
  return [a, b].sort().join('::');
}

function getOrCreate(a: string, b: string): Promise<FingerprintDiffResponse | null> {
  const k = diffKey(a, b);
  const existing = cache.get(k);
  if (existing) return existing;
  const p = fetchFingerprintDiff(a, b).catch(() => null);
  cache.set(k, p);
  return p;
}

export function useFingerprintDiff({
  a,
  b,
}: UseFingerprintDiffArgs): UseFingerprintDiffResult {
  const [data, setData] = useState<FingerprintDiffResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<'not-found' | 'network' | null>(null);

  useEffect(() => {
    if (!a || !b) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    setData(null);
    getOrCreate(a, b).then((payload) => {
      if (cancelled) return;
      if (payload === null) {
        setError('not-found');
      } else {
        setData(payload);
      }
    }).catch(() => {
      if (!cancelled) setError('network');
    }).finally(() => {
      if (!cancelled) setIsLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [a, b]);

  return { data, isLoading, error };
}