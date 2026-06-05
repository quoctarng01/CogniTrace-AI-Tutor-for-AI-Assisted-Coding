/**
 * useStreamingExplanation — SSE connection for LLM explanation streaming.
 *
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Connection state tracking
 * - Graceful error handling with user-friendly messages
 * - Proper cleanup on unmount
 */

import { useState, useCallback, useRef, useEffect } from 'react';

export type ExplanationState = 'idle' | 'connecting' | 'streaming' | 'done' | 'error';

export interface ExplanationParams {
  code: string;
  line_number: number;
  line_content: string;
  locals: Record<string, { type: string; value: string }>;
}

export interface UseStreamingExplanationReturn {
  text: string;
  state: ExplanationState;
  error: string | null;
  provider: string | null;
  start: (params: ExplanationParams) => void;
  stop: () => void;
  retry: () => void;
}

const MAX_RETRIES = 3;
const BASE_RETRY_DELAY_MS = 1000;

export function useStreamingExplanation(apiBaseUrl?: string): UseStreamingExplanationReturn {
  const baseUrl = apiBaseUrl ?? process.env.NEXT_PUBLIC_API_URL ?? '/api';
  const [text, setText] = useState('');
  const [state, setState] = useState<ExplanationState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const currentParamsRef = useRef<ExplanationParams | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
  }, []);

  const start = useCallback(
    (params: ExplanationParams) => {
      // Stop any existing connection
      cleanup();
      currentParamsRef.current = params;
      retryCountRef.current = 0;

      setText('');
      setError(null);
      setProvider(null);
      setState('connecting');

      const query = new URLSearchParams({
        code: params.code,
        line_number: String(params.line_number),
        line_content: params.line_content,
        locals_json: JSON.stringify(params.locals),
      });

      const url = `${baseUrl}/api/llm/explain/stream?${query.toString()}`;
      const es = new EventSource(url);

      es.onopen = () => {
        setState('streaming');
      };

      es.onmessage = (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          if (data.token) {
            setText(prev => prev + data.token);
          }
          if (data.provider) {
            setProvider(data.provider);
          }
        } catch {
          // Non-JSON message, append directly
          setText(prev => prev + e.data);
        }
      };

      // Custom done event
      es.addEventListener('done', () => {
        setState('done');
        cleanup();
      });

      // Custom error event
      es.addEventListener('error', (e: MessageEvent) => {
        const errorData = e.data ? JSON.parse(e.data) : {};
        const errorMessage =
          errorData.message || 'Failed to generate explanation. Please try again.';
        setError(errorMessage);
        setState('error');

        // Attempt retry with exponential backoff
        if (retryCountRef.current < MAX_RETRIES) {
          retryCountRef.current += 1;
          const delay = BASE_RETRY_DELAY_MS * Math.pow(2, retryCountRef.current - 1);

          setState('connecting');
          retryTimeoutRef.current = setTimeout(() => {
            if (currentParamsRef.current) {
              start(currentParamsRef.current);
            }
          }, delay);
        } else {
          cleanup();
        }
      });

      // Network error (EventSource.onerror)
      es.onerror = () => {
        // EventSource errors are handled by the "error" custom event
        // If we receive onerror without a custom event, try reconnecting
        if (state !== 'error') {
          setError('Connection lost. Attempting to reconnect...');
          if (retryCountRef.current < MAX_RETRIES) {
            retryCountRef.current += 1;
            const delay = BASE_RETRY_DELAY_MS * Math.pow(2, retryCountRef.current - 1);
            retryTimeoutRef.current = setTimeout(() => {
              if (currentParamsRef.current) {
                start(currentParamsRef.current);
              }
            }, delay);
          } else {
            setError('Connection failed after multiple attempts. Please try again.');
            setState('error');
            cleanup();
          }
        }
      };

      eventSourceRef.current = es;
    },
    [apiBaseUrl, cleanup, state]
  );

  const stop = useCallback(() => {
    cleanup();
    setState('idle');
    setText('');
    currentParamsRef.current = null;
  }, [cleanup]);

  const retry = useCallback(() => {
    if (currentParamsRef.current) {
      retryCountRef.current = 0;
      start(currentParamsRef.current);
    }
  }, [start]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return {
    text,
    state,
    error,
    provider,
    start,
    stop,
    retry,
  };
}
