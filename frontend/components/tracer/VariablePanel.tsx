'use client';

import { useEffect, useRef, useCallback } from 'react';
import type { TraceStep } from '@/types/trace';
import { getTypeColor } from '@/types/trace';
import styles from './VariablePanel.module.css';
import { MemoryVisualizer } from './MemoryVisualizer';

interface VariablePanelProps {
  variables: Record<string, { type: string; value: string; changed: boolean }>;
  branches?: Record<string, unknown>;
  isLoading?: boolean;
}

export function VariablePanel({ variables, branches, isLoading }: VariablePanelProps) {
  const prevVariablesRef = useRef<
    Record<string, { type: string; value: string; changed: boolean }>
  >({});
  const containerRef = useRef<HTMLDivElement>(null);

  // Track which variables just changed for animation
  const changedVars = Object.entries(variables).filter(
    ([name]) => prevVariablesRef.current[name]?.value !== variables[name]?.value
  );

  useEffect(() => {
    prevVariablesRef.current = variables;
  });

  const sortedVars = Object.entries(variables).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className={styles.panel} ref={containerRef}>
      <div className={styles.header}>
        <h3 className={styles.title}>Variables</h3>
        {isLoading && <span className={styles.loadingDot}>●</span>}
      </div>

      {Object.keys(variables).length === 0 && !isLoading ? (
        <div className={styles.empty}>
          <svg
            width="40"
            height="40"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18" />
          </svg>
          <p>Run the trace to see variable states</p>
        </div>
      ) : (
        <div className={styles.varList}>
          {sortedVars.map(([name, info]) => (
            <div
              key={name}
              className={`${styles.varItem} ${info.changed || changedVars.some(([n]) => n === name) ? styles.changed : ''}`}
            >
              <div className={styles.varHeader}>
                <span className={styles.varName}>{name}</span>
                <span
                  className={styles.typeBadge}
                  style={{
                    backgroundColor: `${getTypeColor(info.type)}20`,
                    color: getTypeColor(info.type),
                  }}
                >
                  {info.type}
                </span>
              </div>
              <div className={styles.varValue}>
                <MemoryVisualizer type={info.type} value={info.value} name={name} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Branch decision display */}
      {branches && Object.keys(branches).length > 0 && (
        <div className={styles.branchSection}>
          <h4 className={styles.branchTitle}>Branch Decision</h4>
          {Object.entries(branches).map(([branchType, branchData]) => (
            <div key={branchType} className={styles.branchInfo}>
              {renderBranch({
                type: branchType,
                ...(branchData as Record<string, unknown>),
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function renderBranch(branch: Record<string, unknown>): React.ReactNode {
  const type = branch.type as string;

  switch (type) {
    case 'if':
      return (
        <div className={styles.branchCard}>
          <div className={styles.branchType}>
            <span className={styles.branchIcon}>⚖</span>
            {branch.taken === true ? (
              <span className={styles.branchTakenTrue}>if branch taken</span>
            ) : branch.taken === false ? (
              <span className={styles.branchTakenFalse}>else branch taken</span>
            ) : null}
          </div>
          {typeof branch.line === 'number' && (
            <span className={styles.branchLine}>line {branch.line}</span>
          )}
        </div>
      );

    case 'for':
      return (
        <div className={styles.branchCard}>
          <div className={styles.branchType}>
            <span className={styles.branchIcon}>🔄</span>
            <span>for loop</span>
          </div>
          {typeof branch.iteration === 'number' && (
            <span className={styles.branchIteration}>iteration {branch.iteration}</span>
          )}
          {typeof branch.line === 'number' && (
            <span className={styles.branchLine}>line {branch.line}</span>
          )}
        </div>
      );

    case 'while':
      return (
        <div className={styles.branchCard}>
          <div className={styles.branchType}>
            <span className={styles.branchIcon}>⟳</span>
            <span>while loop</span>
          </div>
        </div>
      );

    case 'bool_op':
      return (
        <div className={styles.branchCard}>
          <div className={styles.branchType}>
            <span className={styles.branchIcon}>∧∨</span>
            <span>boolean short-circuit</span>
          </div>
        </div>
      );

    case 'ternary_or_if':
      return (
        <div className={styles.branchCard}>
          <div className={styles.branchType}>
            <span className={styles.branchIcon}>?:</span>
            <span>ternary / conditional</span>
          </div>
        </div>
      );

    default:
      return (
        <div className={styles.branchCard}>
          <span>{type}</span>
        </div>
      );
  }
}
