'use client';
/**
 * Purpose: Lazy-fetch + cache a trace's fingerprint on the client. Used by
 *          list views (dashboard, review queue) where each row needs its own
 *          FingerprintBadge but the parent shouldn't fan out N requests
 *          from a single useEffect. Caches the promise in a module-level Map
 *          so multiple cards sharing the same trace id hit the wire once.
 *
 *          Returns `null` while loading or on error — the badge consumers
 *          should treat null as "show nothing" rather than a placeholder,
 *          so a failed backend never blocks the page.
 * Collaborators: lib/api.fetchFingerprint
 * Last significant change: Workstream 12 (Trace Fingerprint)
 */
import { useEffect, useState } from 'react';
import { fetchFingerprint } from '@/lib/api';
import type { FingerprintPayload } from '@/types/fingerprint';

// Module-level promise cache — keyed by trace id. Multiple components
// mounting simultaneously share the same fetch.
const cache = new Map<string, Promise<FingerprintPayload | null>>();

function getOrCreate(traceId: string): Promise<FingerprintPayload | null> {
  const existing = cache.get(traceId);
  if (existing) return existing;
  const p = fetchFingerprint(traceId).catch(() => null);
  cache.set(traceId, p);
  return p;
}

export function useFingerprint(traceId: string | null | undefined): FingerprintPayload | null {
  const [fp, setFp] = useState<FingerprintPayload | null>(null);

  useEffect(() => {
    if (!traceId) {
      setFp(null);
      return;
    }
    let cancelled = false;
    getOrCreate(traceId).then((payload) => {
      if (!cancelled) setFp(payload);
    });
    return () => {
      cancelled = true;
    };
  }, [traceId]);

  return fp;
}
