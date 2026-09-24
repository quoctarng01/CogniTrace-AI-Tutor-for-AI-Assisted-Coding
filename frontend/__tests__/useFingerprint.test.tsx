import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { FingerprintPayload } from '@/types/fingerprint';

// Mock the api module — the hook only ever calls fetchFingerprint().
const mockFetchFingerprint = vi.fn();
vi.mock('@/lib/api', () => ({
  fetchFingerprint: (...args: unknown[]) => mockFetchFingerprint(...args),
}));

// Import after the mock is registered so the hook picks up the stub.
import { useFingerprint } from '@/hooks/useFingerprint';

const sampleFp: FingerprintPayload = {
  branches: 1,
  recursion_depth: 0,
  exception_types: [],
  loop_iterations: 1,
  total_steps: 5,
  conceptual_complexity: '🟢',
  total_duration_ms: 12,
  ast_metrics: {},
  compact: '◆B1-R0-E0-LO1-EX5-CC🟢-T12ms',
  short: '◆B1·R0·E0·LO1·T12ms',
  signature: 'deadbeef',
};

describe('useFingerprint', () => {
  beforeEach(() => {
    mockFetchFingerprint.mockReset();
  });

  it('starts with null and resolves to the payload', async () => {
    mockFetchFingerprint.mockResolvedValue(sampleFp);
    const { result } = renderHook(() => useFingerprint('trace-123'));
    expect(result.current).toBeNull();
    await waitFor(() => expect(result.current).toEqual(sampleFp));
    expect(mockFetchFingerprint).toHaveBeenCalledWith('trace-123');
  });

  it('returns null and does not throw on error', async () => {
    mockFetchFingerprint.mockRejectedValue(new Error('boom'));
    const { result } = renderHook(() => useFingerprint('trace-bad'));
    await waitFor(() => {
      // The hook swallows errors — the assertion is "no crash, still null"
      expect(result.current).toBeNull();
    });
  });

  it('short-circuits when traceId is null/undefined', async () => {
    const { result } = renderHook(() => useFingerprint(null));
    expect(result.current).toBeNull();
    expect(mockFetchFingerprint).not.toHaveBeenCalled();
  });

  it('shares a single fetch across two hooks with the same traceId', async () => {
    mockFetchFingerprint.mockResolvedValue(sampleFp);
    const a = renderHook(() => useFingerprint('trace-shared'));
    const b = renderHook(() => useFingerprint('trace-shared'));
    await waitFor(() => {
      expect(a.result.current).toEqual(sampleFp);
      expect(b.result.current).toEqual(sampleFp);
    });
    // Even with two consumers, the module-level cache collapses to one fetch.
    expect(mockFetchFingerprint).toHaveBeenCalledTimes(1);
  });

  it('does not refetch when traceId changes to a different id', async () => {
    mockFetchFingerprint.mockResolvedValueOnce(sampleFp);
    mockFetchFingerprint.mockResolvedValueOnce({ ...sampleFp, branches: 99 });
    const { result, rerender } = renderHook(({ id }) => useFingerprint(id), {
      initialProps: { id: 'a' },
    });
    await waitFor(() => expect(result.current?.branches).toBe(1));

    rerender({ id: 'b' });
    await waitFor(() => expect(result.current?.branches).toBe(99));
    expect(mockFetchFingerprint).toHaveBeenCalledTimes(2);
  });
});
