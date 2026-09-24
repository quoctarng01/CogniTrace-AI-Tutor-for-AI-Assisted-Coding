'use client';
/**
 * MasteryTrajectory — animated SVG visualization of per-concept mastery
 * over time. Used by /dashboard/mastery (THESIS-05 §2).
 *
 * Design goals:
 *   - Self-contained SVG, no external chart library (bundle size + render perf).
 *   - Animation on mount via stroke-dashoffset reveal; pulse on recent_miss.
 *   - Honors prefers-reduced-motion (skips reveal, freezes pulse).
 *   - All data flows in via props — no fetch here. The page handles fetch +
 *     loading + empty + error states; this component is pure render.
 */
import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import type {
  MasteryTrajectory,
  TrajectoryConcept,
  TrajectoryPoint,
} from '@/types/trajectory';
import styles from './MasteryTrajectory.module.css';

interface MasteryTrajectoryProps {
  trajectory: MasteryTrajectory;
  /** Window in days, controls the x-axis label. */
  windowDays?: number;
}

// Layout constants. Kept inline (not in CSS) so the SVG is portable.
const WIDTH = 720;
const HEIGHT = 280;
const PADDING = { top: 24, right: 16, bottom: 36, left: 44 };
const PLOT_W = WIDTH - PADDING.left - PADDING.right;
const PLOT_H = HEIGHT - PADDING.top - PADDING.bottom;

const Y_TICKS = [0, 0.25, 0.5, 0.75, 1.0];
const X_TICK_COUNT = 5;

function formatDate(iso: string): string {
  // YYYY-MM-DD → "Mar 5"
  const [, m, d] = iso.split('-');
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  const idx = Math.max(1, Math.min(12, parseInt(m, 10))) - 1;
  return `${months[idx]} ${parseInt(d, 10)}`;
}

function buildXTicks(
  startIso: string | null,
  endIso: string | null,
  count: number,
): string[] {
  if (!startIso || !endIso) return [];
  const start = new Date(startIso + 'T00:00:00Z').getTime();
  const end = new Date(endIso + 'T00:00:00Z').getTime();
  if (end <= start) return [startIso];
  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    const t = start + ((end - start) * i) / (count - 1);
    const d = new Date(t);
    const iso = d.toISOString().slice(0, 10);
    out.push(iso);
  }
  return out;
}

function xScale(dateIso: string, domain: { start: string; end: string }): number {
  const t = new Date(dateIso + 'T00:00:00Z').getTime();
  const s = new Date(domain.start + 'T00:00:00Z').getTime();
  const e = new Date(domain.end + 'T00:00:00Z').getTime();
  if (e <= s) return PADDING.left + PLOT_W / 2;
  const frac = (t - s) / (e - s);
  return PADDING.left + frac * PLOT_W;
}

function yScale(mastery: number): number {
  const clamped = Math.max(0, Math.min(1, mastery));
  return PADDING.top + (1 - clamped) * PLOT_H;
}

function buildPath(points: TrajectoryPoint[], domain: { start: string; end: string }): string {
  if (points.length === 0) return '';
  return points
    .map((p, i) => {
      const x = xScale(p.date, domain);
      const y = yScale(p.mastery);
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');
}

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}

export function MasteryTrajectory({
  trajectory,
  windowDays = 30,
}: MasteryTrajectoryProps): ReactNode {
  const reduced = useMemo(prefersReducedMotion, []);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Trigger the line-draw animation on next frame
    if (reduced) return;
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, [reduced, trajectory.total_events]);

  const { concepts, date_range, total_events } = trajectory;
  const hasData = concepts.length > 0 && date_range.start && date_range.end;

  const domain = useMemo(
    () => ({ start: date_range.start ?? '', end: date_range.end ?? '' }),
    [date_range.start, date_range.end],
  );

  const xTicks = useMemo(
    () => buildXTicks(date_range.start, date_range.end, X_TICK_COUNT),
    [date_range.start, date_range.end],
  );

  if (!hasData) {
    return (
      <div className={styles.empty}>
        <svg
          width="40"
          height="40"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path d="M3 3v18h18" />
          <path d="M7 14l4-4 3 3 5-5" />
        </svg>
        <p>No mastery data yet.</p>
        <p className={styles.emptyHint}>
          Review a few cards and your concept-by-concept trajectory will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.wrapper}>
      <header className={styles.header}>
        <h3 className={styles.title}>Concept mastery trajectory</h3>
        <p className={styles.subtitle}>
          {concepts.length} concept{concepts.length === 1 ? '' : 's'} ·
          {' '}{total_events} review{total_events === 1 ? '' : 's'} ·
          {' '}last {windowDays} days
        </p>
      </header>

      <svg
        role="img"
        aria-label={`Concept mastery trajectory over the last ${windowDays} days, showing ${concepts.length} concept line${concepts.length === 1 ? '' : 's'}.`}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className={styles.chart}
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Y-axis grid + labels */}
        {Y_TICKS.map(tick => (
          <g key={tick}>
            <line
              x1={PADDING.left}
              x2={PADDING.left + PLOT_W}
              y1={yScale(tick)}
              y2={yScale(tick)}
              className={styles.gridLine}
            />
            <text
              x={PADDING.left - 8}
              y={yScale(tick)}
              className={styles.axisLabel}
              textAnchor="end"
              dominantBaseline="middle"
            >
              {Math.round(tick * 100)}%
            </text>
          </g>
        ))}

        {/* X-axis ticks */}
        {xTicks.map((iso, i) => (
          <text
            key={iso}
            x={xScale(iso, domain)}
            y={HEIGHT - PADDING.bottom + 18}
            className={styles.axisLabel}
            textAnchor={i === 0 ? 'start' : i === xTicks.length - 1 ? 'end' : 'middle'}
          >
            {formatDate(iso)}
          </text>
        ))}

        {/* Each concept line */}
        {concepts.map(concept => (
          <ConceptLine
            key={concept.concept_tag}
            concept={concept}
            domain={domain}
            animate={mounted}
            reduced={reduced}
          />
        ))}
      </svg>

      <ul className={styles.legend} aria-label="Concept legend">
        {concepts.map(concept => (
          <li key={concept.concept_tag} className={styles.legendItem}>
            <span
              className={styles.swatch}
              style={{ backgroundColor: concept.color } as CSSProperties}
              aria-hidden="true"
            />
            <span className={styles.legendTag}>{concept.concept_tag}</span>
            <span className={styles.legendMeta}>
              {Math.round(concept.current_mastery * 100)}%
              {concept.recent_miss ? (
                <span
                  className={styles.missPill}
                  aria-label="recent miss"
                  title="Recent 'hard' or 'again' rating"
                >
                  ●
                </span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface ConceptLineProps {
  concept: TrajectoryConcept;
  domain: { start: string; end: string };
  animate: boolean;
  reduced: boolean;
}

function ConceptLine({
  concept,
  domain,
  animate,
  reduced,
}: ConceptLineProps): ReactNode {
  const path = useMemo(() => buildPath(concept.points, domain), [concept.points, domain]);
  const last = concept.points[concept.points.length - 1];

  return (
    <g className={styles.conceptGroup}>
      <path
        d={path}
        fill="none"
        stroke={concept.color}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
        className={[
          styles.line,
          animate && !reduced ? styles.lineDraw : '',
        ]
          .filter(Boolean)
          .join(' ')}
      />
      {/* Per-point markers */}
      {concept.points.map((p, i) => (
        <circle
          key={`${p.date}-${i}`}
          cx={xScale(p.date, domain)}
          cy={yScale(p.mastery)}
          r={3}
          fill={concept.color}
          opacity={0.85}
        />
      ))}
      {/* Final point — pulsing if recent_miss */}
      {last && (
        <circle
          cx={xScale(last.date, domain)}
          cy={yScale(last.mastery)}
          r={concept.recent_miss && !reduced ? 7 : 5}
          fill={concept.color}
          stroke="var(--surface)"
          strokeWidth={2}
          className={concept.recent_miss && !reduced ? styles.pulse : ''}
        >
          {concept.recent_miss && (
            <title>
              {concept.concept_tag}: last 3 days included a "hard" or "again" rating
            </title>
          )}
        </circle>
      )}
    </g>
  );
}
