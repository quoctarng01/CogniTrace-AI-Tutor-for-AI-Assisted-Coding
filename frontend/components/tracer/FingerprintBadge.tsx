'use client';
/**
 * Purpose: Compact chip rendering the trace's compact-form signature plus
 *          the conceptual-complexity traffic light. Designed to be dropped
 *          into share modals, dashboard rows, and review cards.
 * Collaborators: types/fingerprint.ts
 * Last significant change: Workstream 12 (Trace Fingerprint)
 */


import type { ReactNode } from 'react';
import {
  complexityColor,
  complexityBorderColor,
  complexityBucket,
} from '@/types/fingerprint';
import type { FingerprintPayload } from '@/types/fingerprint';

interface FingerprintBadgeProps {
  fingerprint: FingerprintPayload;
  /** When true, expand to a two-line card (used on the share page). */
  detailed?: boolean;
  /** Optional click target — if provided, the badge becomes a button. */
  onClick?: () => void;
  /** Title for tooltip / aria. */
  label?: string;
}

export function FingerprintBadge({
  fingerprint,
  detailed = false,
  onClick,
  label,
}: FingerprintBadgeProps): ReactNode {
  const cc = fingerprint.conceptual_complexity ?? '🟢';
  const bucket = complexityBucket(cc);
  const bg = complexityColor(cc);
  const border = complexityBorderColor(cc);
  const labelText =
    label ?? `Trace fingerprint — ${bucket} complexity`;

  const baseStyle = {
    display: 'inline-flex',
    flexDirection: 'column' as const,
    gap: '4px',
    padding: detailed ? '10px 14px' : '4px 10px',
    borderRadius: '8px',
    background: bg,
    border: `1px solid ${border}`,
    fontFamily:
      'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
    fontSize: detailed ? '12px' : '11px',
    lineHeight: 1.4,
    color: 'var(--text, #1a1a1a)',
    cursor: onClick ? 'pointer' : 'default',
    userSelect: 'text' as const,
  };

  const content = (
    <>
      <span style={{ fontWeight: 600, letterSpacing: '0.02em' }}>
        {fingerprint.compact}
      </span>
      {detailed && (
        <span
          style={{
            fontSize: '10px',
            color: 'var(--text-muted, #555)',
            fontFamily: 'inherit',
          }}
        >
          {fingerprint.branches} branch
          {fingerprint.branches === 1 ? '' : 'es'} ·{' '}
          {fingerprint.recursion_depth} recursive ·{' '}
          {fingerprint.loop_iterations} loop{' '}
          {fingerprint.loop_iterations === 1 ? 'iter' : 'iters'} ·{' '}
          {Math.round(fingerprint.total_duration_ms)}ms
        </span>
      )}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-label={labelText}
        title={labelText}
        style={{
          ...baseStyle,
          font: 'inherit',
          textAlign: 'left',
        }}
      >
        {content}
      </button>
    );
  }

  return (
    <span aria-label={labelText} title={labelText} style={baseStyle}>
      {content}
    </span>
  );
}
