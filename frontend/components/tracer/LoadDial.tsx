/**
 * Purpose: Circular dial that visualises a trace's 0..100 cognitive-load
 *          estimate (T1-A). Renders the aggregate score with a coloured
 *          arc plus a stacked breakdown of the structural / interaction /
 *          SM-2 sub-scores.
 * Collaborators:
 *   - lib/api.ts::fetchTraceLoad (or the local useTraceLoad hook)
 *   - backend/app/services/load_estimator.py
 *   - backend/app/routers/load.py::get_trace_load
 * Last significant change: T1-A (Cognitive Load Dashboard)
 *
 * Design notes:
 *   - The dial is *purely* a presentation layer — the scoring math lives
 *     on the server. Keeping the math server-side means we can re-tune
 *     the weights without shipping a new bundle.
 *   - The colour bands are calibrated against the pilot thresholds in
 *     docs/MEASUREMENT.md §10. The bands are deliberately coarse
 *     (low/med/high) so the dial isn't falsely precise.
 */
'use client';

import type { ReactNode } from 'react';
import type { LoadResponse } from '@/lib/api';
import styles from './LoadDial.module.css';

interface LoadDialProps {
  /** A load response from `fetchTraceLoad`. When null, the dial renders
   *  in its empty state ("no signal yet"). */
  load: LoadResponse | null;
  /** True while the load is being fetched. Lets the parent layer
   *  in a spinner without us duplicating state. */
  loading?: boolean;
  /** Optional error message to surface in place of the dial. */
  error?: string | null;
}

const RADIUS = 56;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function arcOffset(score: number): number {
  const clamped = Math.max(0, Math.min(100, score));
  return CIRCUMFERENCE * (1 - clamped / 100);
}

function loadBand(score: number): { label: string; bandClass: string } {
  if (score < 30) return { label: 'low load', bandClass: 'low' };
  if (score < 60) return { label: 'moderate load', bandClass: 'moderate' };
  if (score < 80) return { label: 'high load', bandClass: 'high' };
  return { label: 'peak load', bandClass: 'peak' };
}

export function LoadDial({
  load,
  loading = false,
  error = null,
}: LoadDialProps): ReactNode {
  if (error) {
    return (
      <div className={styles.dial} role="status" aria-live="polite">
        <p className={styles.error}>{error}</p>
      </div>
    );
  }

  if (loading || !load) {
    return (
      <div className={styles.dial} role="status" aria-live="polite">
        <div className={styles.empty}>
          <span className={styles.spinner} aria-hidden="true">
            ◈
          </span>
          <p>{loading ? 'Measuring cognitive load…' : 'No load signal yet.'}</p>
        </div>
      </div>
    );
  }

  const { score } = load;
  const band = loadBand(score);
  const offset = arcOffset(score);

  return (
    <div className={styles.dial} role="img" aria-label={`Cognitive load: ${score}/100 (${band.label})`}>
      <div
        className={`${styles.gauge} ${styles[band.bandClass]}`}
        data-band={band.bandClass}
      >
        <svg viewBox="0 0 140 140" width={140} height={140}>
          <circle
            cx={70}
            cy={70}
            r={RADIUS}
            strokeWidth={10}
            fill="none"
            className={styles.track}
          />
          <circle
            cx={70}
            cy={70}
            r={RADIUS}
            strokeWidth={10}
            fill="none"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className={styles.fill}
            transform="rotate(-90 70 70)"
          />
          <text x={70} y={70} textAnchor="middle" dy=".32em" className={styles.value}>
            {score}
          </text>
          <text x={70} y={90} textAnchor="middle" className={styles.unit}>
            /100
          </text>
        </svg>
        <span className={styles.bandLabel}>{band.label}</span>
      </div>

      <div className={styles.breakdown} aria-label="load breakdown">
        <Row label="Structural" value={load.structural} />
        <Row label="Interaction" value={load.interaction} />
        <Row label="Concept (SM-2)" value={load.sm2} />
      </div>

      {load.notes && load.notes.length > 0 && (
        <ul className={styles.notes} aria-label="load notes">
          {load.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className={styles.row}>
      <span className={styles.rowLabel}>{label}</span>
      <div className={styles.rowBar}>
        <div
          className={styles.rowFill}
          style={{ width: `${pct}%` }}
          aria-hidden="true"
        />
      </div>
      <span className={styles.rowValue}>{pct}%</span>
    </div>
  );
}
