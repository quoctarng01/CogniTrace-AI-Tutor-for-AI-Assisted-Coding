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
