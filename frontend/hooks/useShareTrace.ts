/**
 * useShareTrace — share-modal state and submit handler.
 *
 * The tracer page has a "Generate share link" modal that asks for an optional
 * password and an optional expiry. Wrapping its state + handlers in a hook
 * removes ~15 lines of plumbing from the page and makes the surface obvious:
 *
 *   const { isOpen, open, close, isSharing, error, result, submit, password,
 *           setPassword, expirationDays, setExpirationDays } = useShareTrace();
 *
 * State ownership:
 *  - visibility (`isOpen`)
 *  - the optional password (`password`)
 *  - the optional expiry in days (`expirationDays`)
 *  - the result returned by the share endpoint (`result`)
 *  - in-flight / error / reset callbacks
 *
 * The hook knows about `shareTrace` from `@/lib/api`; it does NOT know how
 * the result is rendered. The caller passes `traceId` when ready to submit.
 */

import { useCallback, useState } from 'react';
import { shareTrace } from '@/lib/api';
import { trackEvent } from '@/lib/analytics';

export interface ShareResult {
  share_token: string;
  share_url: string;
  expires_at: string | null;
  has_password: boolean;
}

export interface UseShareTraceReturn {
  // visibility
  isOpen: boolean;
  open: () => void;
  close: () => void;
  // form
  password: string;
  setPassword: (next: string) => void;
  expirationDays: number | null;
  setExpirationDays: (next: number | null) => void;
  // submit state
  isSharing: boolean;
  error: string | null;
  result: ShareResult | null;
  submit: (traceId: string) => Promise<void>;
}

export function useShareTrace(): UseShareTraceReturn {
  const [isOpen, setIsOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [expirationDays, setExpirationDays] = useState<number | null>(null);
  const [result, setResult] = useState<ShareResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSharing, setIsSharing] = useState(false);

  const open = useCallback(() => {
    setResult(null);
    setError(null);
    setPassword('');
    setExpirationDays(null);
    setIsOpen(true);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
  }, []);

  const submit = useCallback(
    async (traceId: string) => {
      setIsSharing(true);
      setError(null);
      try {
        const next = await shareTrace(traceId, {
          expiration_days: expirationDays ?? undefined,
          password: password || undefined,
        });
        setResult(next);
        trackEvent('trace_shared', {
          expiration_days: expirationDays,
          has_password: !!password,
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to generate share link';
        setError(message);
      } finally {
        setIsSharing(false);
      }
    },
    [expirationDays, password],
  );

  return {
    isOpen,
    open,
    close,
    password,
    setPassword,
    expirationDays,
    setExpirationDays,
    isSharing,
    error,
    result,
    submit,
  };
}
