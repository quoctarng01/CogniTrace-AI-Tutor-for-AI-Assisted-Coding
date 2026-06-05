const ANON_ID_KEY = 'codescope_anon_id';

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
  fetch('/api/analytics/track', {
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
