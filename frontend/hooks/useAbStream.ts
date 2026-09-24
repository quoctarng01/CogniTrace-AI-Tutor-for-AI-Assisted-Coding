/**
 * useAbStream — SSE hook for the A/B ablation demo.
 *
 * Connects to /api/llm/ab and yields three parallel streams:
 *   - `grounded`  (with trace grounding — the "treatment")
 *   - `blind`     (without grounding — the "control", RQ1 Condition A)
 *   - `verdict`   (judge's per-side 0/1/2 score + reasoning + winner)
 *
 * The hook matches the style of `useStreamingExplanation.ts` so the rest of
 * the codebase stays consistent. It does *not* auto-retry on transient
 * network errors: a failed ablation is a failed demo and the operator
 * should see the error banner.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export type AbState = 'idle' | 'connecting' | 'streaming' | 'done' | 'error';

export interface AbParams {
  code: string;
  line_number: number;
  line_content: string;
  locals: Record<string, { type: string; value: string }>;
  token?: string | null;
}

export interface AbVerdict {
  blind_score: 0 | 1 | 2;
  blind_reasoning: string;
  grounded_score: 0 | 1 | 2;
  grounded_reasoning: string;
  winner: 'grounded' | 'blind' | 'tie';
}

export interface UseAbStreamReturn {
  grounded: string;
  blind: string;
  groundedProvider: string | null;
  blindProvider: string | null;
  verdict: AbVerdict | null;
  state: AbState;
  error: string | null;
  start: (params: AbParams) => void;
  stop: () => void;
  reset: () => void;
}

export function useAbStream(apiBaseUrl?: string): UseAbStreamReturn {
  const baseUrl = apiBaseUrl ?? process.env.NEXT_PUBLIC_API_URL ?? '/api';

  const [grounded, setGrounded] = useState('');
  const [blind, setBlind] = useState('');
  const [groundedProvider, setGroundedProvider] = useState<string | null>(null);
  const [blindProvider, setBlindProvider] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<AbVerdict | null>(null);
  const [state, setState] = useState<AbState>('idle');
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const currentParamsRef = useRef<AbParams | null>(null);

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const start = useCallback(
    (params: AbParams) => {
      cleanup();
      currentParamsRef.current = params;

      setGrounded('');
      setBlind('');
      setGroundedProvider(null);
      setBlindProvider(null);
      setVerdict(null);
      setError(null);
      setState('connecting');

      const queryParams: Record<string, string> = {
        code: params.code,
        line_number: String(params.line_number),
        line_content: params.line_content,
        locals_json: JSON.stringify(params.locals),
      };
      if (params.token) {
        queryParams.token = params.token;
      }

      const query = new URLSearchParams(queryParams);
      const url = `${baseUrl}/api/llm/ab?${query.toString()}`;
      const es = new EventSource(url);

      es.onopen = () => setState('streaming');

      es.addEventListener('grounded', (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          if (typeof data.token === 'string') {
            setGrounded((prev) => prev + data.token);
          }
          if (data.provider) setGroundedProvider(data.provider);
        } catch {
          // ignore malformed events
        }
      });

      es.addEventListener('blind', (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          if (typeof data.token === 'string') {
            setBlind((prev) => prev + data.token);
          }
          if (data.provider) setBlindProvider(data.provider);
        } catch {
          // ignore
        }
      });

      es.addEventListener('grounded_done', (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          if (data.provider) setGroundedProvider(data.provider);
        } catch {
          // ignore
        }
      });

      es.addEventListener('blind_done', (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          if (data.provider) setBlindProvider(data.provider);
        } catch {
          // ignore
        }
      });

      es.addEventListener('verdict', (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as AbVerdict;
          setVerdict(data);
        } catch {
          // ignore
        }
      });

      es.addEventListener('done', () => {
        setState('done');
        cleanup();
      });

      es.addEventListener('error', (e: MessageEvent) => {
        try {
          const data = e.data ? JSON.parse(e.data) : null;
          setError(data?.message ?? 'A/B stream error.');
        } catch {
          setError('A/B stream error.');
        }
        setState('error');
        cleanup();
      });

      // Network-level error (EventSource fires onerror on connection drop)
      es.onerror = () => {
        if (state !== 'error') {
          setError('Connection lost during A/B stream.');
          setState('error');
          cleanup();
        }
      };

      eventSourceRef.current = es;
    },
    [baseUrl, cleanup, state],
  );

  const stop = useCallback(() => {
    cleanup();
    setState('idle');
    currentParamsRef.current = null;
  }, [cleanup]);

  const reset = useCallback(() => {
    cleanup();
    setGrounded('');
    setBlind('');
    setGroundedProvider(null);
    setBlindProvider(null);
    setVerdict(null);
    setError(null);
    setState('idle');
    currentParamsRef.current = null;
  }, [cleanup]);

  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  return {
    grounded,
    blind,
    groundedProvider,
    blindProvider,
    verdict,
    state,
    error,
    start,
    stop,
    reset,
  };
}
