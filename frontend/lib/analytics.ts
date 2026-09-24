/**
 * Purpose: Client-side analytics shim — wraps PostHog / custom events behind a stable interface.
 * Collaborators: —
 * Last significant change: Workstream 9
 */

const ANON_ID_KEY = 'cognitrace_anon_id';
const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000') + '/api';

export function getAnonId(): string {
  if (typeof window === 'undefined') return '';
  let id = localStorage.getItem(ANON_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(ANON_ID_KEY, id);
  }
  return id;
}

export function trackEvent(type: string, metadata?: Record<string, unknown>) {
  fetch(`${API_BASE}/analytics/track`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      anon_id: getAnonId(),
      event_type: type,
      metadata,
      occurred_at: new Date().toISOString(),
    }),
  }).catch(() => {}); // Never block UX
}

/* ── T1-A: Cognitive Load Dashboard — typed load events ────────────── *
 *
 * The dashboard's load estimator (`backend/app/services/load_estimator.py`)
 * consumes these events via the `anonymous_events` table. All events
 * carry a `trace_id` so the load endpoint can correlate them with a
 * single trace session. Names are stable — changing them is a breaking
 * measurement-side change (see `docs/MEASUREMENT.md` §10).
 */

export type LoadEventType =
  | 'tracer_pause'           // student paused scrolling on a line for ≥2s
  | 'tracer_resume'          // student resumed scrolling
  | 'tracer_whatif_replay'   // student rewound without modifying code
  | 'tutor_checkpoint_miss'; // student got a checkpoint wrong (alias of tutor_checkpoint_submitted{correct:false})

/** Emit a typed load-bearing interaction event. */
export function trackLoadEvent(
  type: LoadEventType,
  payload: { trace_id: string; duration_ms?: number; line?: number } & Record<string, unknown>
): void {
  trackEvent(type, payload);
}

