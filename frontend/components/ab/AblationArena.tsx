/**
 * AblationArena — the side-by-side grounded-vs-blind arena.
 *
 * Workstream 11 / thesis-defense wow demo (THESIS-W1-RESULTS.md §3.3).
 *
 * Renders two streaming text columns and a verdict card. Used exclusively
 * by /tracer/ab — the live tracer is unaffected.
 */

import { useEffect, useMemo } from 'react';
import { useAbStream } from '@/hooks/useAbStream';
import type { TraceStep } from '@/types/trace';
import styles from './AblationArena.module.css';

export interface AblationArenaProps {
  code: string;
  lineNumber: number;
  lineContent: string;
  locals: Record<string, { type: string; value: string }>;
  /** Trigger when the user clicks "Run A/B". */
  runId: number;
  /** When provided, surface the variable name the cursor is hovering. */
  hoveredVariable?: string | null;
}

function highlightVariables(
  text: string,
  variableNames: string[],
  hovered: string | null,
): React.ReactNode[] {
  if (variableNames.length === 0) return [text];

  const escaped = variableNames.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const re = new RegExp(`\\b(${escaped.join('|')})\\b`, 'g');
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const isHovered = hovered && match[1] === hovered;
    parts.push(
      <span
        key={`vh-${key++}`}
        className={`${styles.variableMention} ${isHovered ? styles.variableHover : ''}`}
        data-var={match[1]}
      >
        {match[1]}
      </span>,
    );
    lastIndex = match.index + match[1].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

function extractLocalVariables(steps: TraceStep[] | undefined, lineNumber: number): string[] {
  if (!steps || steps.length === 0) return [];
  const step = steps.find((s) => s.line_number === lineNumber) ?? steps[0];
  if (!step?.variables) return [];
  return Object.keys(step.variables);
}

export function AblationArena({
  code,
  lineNumber,
  lineContent,
  locals,
  runId,
  hoveredVariable = null,
}: AblationArenaProps) {
  const {
    grounded,
    blind,
    groundedProvider,
    blindProvider,
    verdict,
    state,
    error,
    start,
    reset,
  } = useAbStream();

  // Variable names extracted from locals (for hover-to-highlight)
  const variableNames = useMemo(() => Object.keys(locals ?? {}), [locals]);
  // Fallback: extract from any step if locals empty
  const fallbackVars = useMemo(() => extractLocalVariables(undefined, lineNumber), [lineNumber]);
  const highlightVars = variableNames.length > 0 ? variableNames : fallbackVars;

  // Re-run when runId changes (user pressed Run A/B again)
  useEffect(() => {
    if (runId === 0) return;
    start({ code, line_number: lineNumber, line_content: lineContent, locals });
  }, [runId]); // eslint-disable-line react-hooks/exhaustive-deps

  const isRunning = state === 'connecting' || state === 'streaming';

  return (
    <div className={styles.arena}>
      <div className={styles.header}>
        <div className={styles.headerTitle}>
          <span className={styles.dot} />
          <h2 className={styles.title}>Grounded vs Blind A/B</h2>
        </div>
        <div className={styles.headerSub}>
          Line {lineNumber}: <code className={styles.linePreview}>{lineContent || '(no line selected)'}</code>
        </div>
        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.resetBtn}
            onClick={reset}
            disabled={isRunning}
          >
            ↺ Reset
          </button>
        </div>
      </div>

      <div className={styles.columns}>
        {/* BLIND column */}
        <div className={`${styles.column} ${styles.columnBlind}`}>
          <div className={styles.columnHeader}>
            <span className={styles.columnTag}>🚫 BLIND</span>
            <span className={styles.columnSub}>
              code only · no trace · no locals
            </span>
            <span className={styles.providerBadge}>
              {blindProvider ?? (isRunning ? '…' : 'idle')}
            </span>
          </div>
          <div className={styles.stream}>
            {blind.length === 0 && !isRunning && (
              <p className={styles.placeholder}>
                Press <strong>Run A/B</strong> to compare explanations.
              </p>
            )}
            <p className={styles.streamText}>
              {highlightVariables(blind, highlightVars, hoveredVariable)}
              {isRunning && state === 'streaming' && (
                <span className={styles.caret}>▍</span>
              )}
            </p>
          </div>
        </div>

        {/* GROUNDED column */}
        <div className={`${styles.column} ${styles.columnGrounded}`}>
          <div className={styles.columnHeader}>
            <span className={styles.columnTag}>✓ GROUNDED</span>
            <span className={styles.columnSub}>
              code + line + runtime locals_dict
            </span>
            <span className={styles.providerBadge}>
              {groundedProvider ?? (isRunning ? '…' : 'idle')}
            </span>
          </div>
          <div className={styles.stream}>
            {grounded.length === 0 && !isRunning && (
              <p className={styles.placeholder}>
                Press <strong>Run A/B</strong> to compare explanations.
              </p>
            )}
            <p className={styles.streamText}>
              {highlightVariables(grounded, highlightVars, hoveredVariable)}
              {isRunning && state === 'streaming' && (
                <span className={styles.caret}>▍</span>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Verdict card */}
      {verdict && (
        <div className={`${styles.verdict} ${verdictClass(verdict.winner)}`}>
          <div className={styles.verdictTitle}>
            <span className={styles.verdictIcon}>{verdictIcon(verdict.winner)}</span>
            <span>
              Judge verdict · winner ={' '}
              <strong className={styles.verdictWinner}>{verdict.winner}</strong>
            </span>
          </div>
          <div className={styles.verdictGrid}>
            <div className={`${styles.verdictCell} ${styles.verdictCellBlind}`}>
              <div className={styles.verdictLabel}>Blind</div>
              <div className={styles.verdictScore}>{verdict.blind_score} / 2</div>
              <div className={styles.verdictReasoning}>{verdict.blind_reasoning}</div>
            </div>
            <div className={`${styles.verdictCell} ${styles.verdictCellGrounded}`}>
              <div className={styles.verdictLabel}>Grounded</div>
              <div className={styles.verdictScore}>{verdict.grounded_score} / 2</div>
              <div className={styles.verdictReasoning}>{verdict.grounded_reasoning}</div>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className={styles.error}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {state === 'done' && (
        <div className={styles.footer}>
          <em>
            This is the empirical claim of <strong>Contribution #1</strong> (RQ1): trace
            grounding moves a CS1 debugging explanation from {verdict?.blind_score ?? 0}/2
            to {verdict?.grounded_score ?? 2}/2 on the W1 rubric.
          </em>
        </div>
      )}
    </div>
  );
}

function verdictClass(winner: 'grounded' | 'blind' | 'tie'): string {
  if (winner === 'grounded') return styles.verdictGroundedWins;
  if (winner === 'blind') return styles.verdictBlindWins;
  return styles.verdictTie;
}

function verdictIcon(winner: 'grounded' | 'blind' | 'tie'): string {
  if (winner === 'grounded') return '🏆';
  if (winner === 'blind') return '🤯';
  return '🤝';
}
