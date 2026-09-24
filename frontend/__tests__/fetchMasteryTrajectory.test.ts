/**
 * Tests for fetchMasteryTrajectory's soft-fail behavior.
 *
 * The trajectory endpoint can return 404 if the backend hasn't been
 * restarted to pick up the new route, or 401 if the user's session
 * expired. Both cases should produce an empty trajectory (which the
 * page renders as the friendly "No mastery data yet" state) — not a
 * loud error banner with a leaked API key like MASTERY_TRAJECTORY_NOT_FOUND.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Supabase is already mocked in __tests__/setup.ts. We just need to
// stub global.fetch to control the HTTP layer.
const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('fetchMasteryTrajectory', () => {
  it('returns the parsed body on a 2xx response', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, {
        concepts: [
          {
            concept_tag: 'alpha',
            color: '#7c3aed',
            total_reviews: 1,
            current_mastery: 0.5,
            recent_miss: false,
            points: [
              { date: '2026-01-01', mastery: 0.5, rating: 'good', repetitions: 1, interval_days: 6 },
            ],
          },
        ],
        date_range: { start: '2026-01-01', end: '2026-01-01' },
        total_events: 1,
        days: 30,
      }),
    );
    const { fetchMasteryTrajectory } = await import('@/lib/api');
    const t = await fetchMasteryTrajectory(30);
    expect(t.concepts).toHaveLength(1);
    expect(t.concepts[0].concept_tag).toBe('alpha');
  });

  it('returns an empty trajectory on 404 (route missing / no data)', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(404));
    const { fetchMasteryTrajectory } = await import('@/lib/api');
    const t = await fetchMasteryTrajectory(30);
    expect(t.concepts).toEqual([]);
    expect(t.total_events).toBe(0);
    expect(t.date_range).toEqual({ start: null, end: null });
    expect(t.days).toBe(30);
  });

  it('returns an empty trajectory on 401 (session expired)', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(401));
    const { fetchMasteryTrajectory } = await import('@/lib/api');
    const t = await fetchMasteryTrajectory(30);
    expect(t.concepts).toEqual([]);
    expect(t.total_events).toBe(0);
  });

  it('echoes back the requested window in the empty trajectory', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(404));
    const { fetchMasteryTrajectory } = await import('@/lib/api');
    const t = await fetchMasteryTrajectory(7);
    expect(t.days).toBe(7);
  });

  it('throws on 500 (real server error should surface to the user)', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(500, { detail: 'kaboom' }),
    );
    const { fetchMasteryTrajectory } = await import('@/lib/api');
    await expect(fetchMasteryTrajectory(30)).rejects.toThrow();
  });
});
