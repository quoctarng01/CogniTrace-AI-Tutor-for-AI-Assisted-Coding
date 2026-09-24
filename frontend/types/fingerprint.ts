/**
 * Trace Fingerprint — thesis Contribution #4.
 *
 * A deterministic, human-readable signature for a Python trace. Computed in
 * ~1 ms by a pure-Python AST classifier (no LLM); stored in
 * `trace_fingerprints`; served via `/api/traces/{id}/fingerprint` and
 * `/api/fingerprint/{share_token}`. The compact / short / signature fields
 * are the public-facing surface — the rest of the wire payload is for the
 * detail view and analytics.
 */
export interface FingerprintPayload {
  branches: number;
  recursion_depth: number;
  exception_types: string[];
  loop_iterations: number;
  total_steps: number;
  /** One of 🟢, 🟡, 🔴. */
  conceptual_complexity: '🟢' | '🟡' | '🔴' | string;
  total_duration_ms: number;
  ast_metrics: Record<string, number>;
  /** e.g. "◆B2-R3-E1-LO2-EX2-CC🟢-T47ms". */
  compact: string;
  /** e.g. "◆B2·R3·E1·LO2·T47ms" — OG-card friendly (no emoji, no exception). */
  short: string;
  /** SHA-1 short hash of the canonical JSON. */
  signature: string;
}

/** Translate a conceptual complexity emoji to a labelled bucket. */
export function complexityBucket(cc: string): 'green' | 'yellow' | 'red' {
  if (cc === '🔴') return 'red';
  if (cc === '🟡') return 'yellow';
  return 'green';
}

/** CSS colour used by FingerprintBadge for the chip background. */
export function complexityColor(cc: string): string {
  switch (complexityBucket(cc)) {
    case 'red':
      return 'var(--danger-bg, #fde2e2)';
    case 'yellow':
      return 'var(--warning-bg, #fff3cd)';
    default:
      return 'var(--success-bg, #d4f4dd)';
  }
}

/** Foreground / border colour for the chip. */
export function complexityBorderColor(cc: string): string {
  switch (complexityBucket(cc)) {
    case 'red':
      return 'var(--danger, #b91c1c)';
    case 'yellow':
      return 'var(--warning, #b45309)';
    default:
      return 'var(--success, #047857)';
  }
}

// ── T1-D: Trace diff types (THESIS-05 §4) ────────────────────────────

export interface FingerprintDiffDelta {
  field: string;
  label: string;
  a_value: number | string | string[];
  b_value: number | string | string[];
  narrative: string;
  significant: boolean;
}

export interface FingerprintDiffResponse {
  a: FingerprintPayload;
  b: FingerprintPayload;
  a_kind: 'share_token' | 'trace_id';
  b_kind: 'share_token' | 'trace_id';
  deltas: FingerprintDiffDelta[];
  summary: string;
  identical: boolean;
}
