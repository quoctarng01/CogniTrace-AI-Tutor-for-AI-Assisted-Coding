"use client";

import { useState, useCallback } from 'react';
import type { TraceStep } from '@/types/trace';
import styles from './WhatIfModal.module.css';

interface WhatIfModalProps {
  steps: TraceStep[];
  code: string;
  onSubmit: (initialNamespace: Record<string, string>, changedVars: string[]) => void;
  onClose: () => void;
  isLoading?: boolean;
}

type VarType = 'string' | 'number' | 'list' | 'dict' | 'bool' | 'null' | 'unknown';

function detectType(valueStr: string): VarType {
  const trimmed = valueStr.trim();
  if (trimmed === 'True' || trimmed === 'False') return 'bool';
  if (trimmed === 'None') return 'null';
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) return 'list';
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) return 'dict';
  if (trimmed.startsWith('"') || trimmed.startsWith("'")) return 'string';
  if (!isNaN(Number(trimmed)) && trimmed !== '') return 'number';
  return 'unknown';
}

function TypeInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const varType = detectType(value);

  if (varType === 'list' || varType === 'dict') {
    return (
      <textarea
        className={styles.textareaInput}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        placeholder={varType === 'list' ? '[1, 2, 3]' : '{"key": "value"}'}
      />
    );
  }
  if (varType === 'bool') {
    return (
      <select className={styles.selectInput} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="True">True</option>
        <option value="False">False</option>
      </select>
    );
  }
  if (varType === 'number') {
    return (
      <input
        type="number"
        className={styles.textInput}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  return (
    <input
      type="text"
      className={styles.textInput}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={value || 'Enter value...'}
    />
  );
}

export function WhatIfModal({ steps, code, onSubmit, onClose, isLoading }: WhatIfModalProps) {
  const firstStep = steps[0];
  const initialVars = firstStep?.variables ?? {};

  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const [name, info] of Object.entries(initialVars)) {
      init[name] = info.value;
    }
    return init;
  });

  const [changedVars, setChangedVars] = useState<Set<string>>(new Set());

  const handleChange = useCallback(
    (name: string, newValue: string) => {
      setValues((prev) => ({ ...prev, [name]: newValue }));
      if (newValue !== initialVars[name]?.value) {
        setChangedVars((prev) => new Set(prev).add(name));
      } else {
        setChangedVars((prev) => {
          const next = new Set(prev);
          next.delete(name);
          return next;
        });
      }
    },
    [initialVars]
  );

  const handleSubmit = useCallback(() => {
    onSubmit(values, Array.from(changedVars));
  }, [values, changedVars, onSubmit]);

  const changedList = Array.from(changedVars);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>What If?</h2>
          <p className={styles.subtitle}>
            Modify initial values and see how the execution changes.
          </p>
        </div>

        <div className={styles.variables}>
          {Object.keys(initialVars).length === 0 ? (
            <p className={styles.noVars}>No variables detected at step 0.</p>
          ) : (
            Object.entries(initialVars).map(([name, info]) => (
              <div key={name} className={styles.varRow}>
                <div className={styles.varHeader}>
                  <span className={`${styles.varName} ${changedVars.has(name) ? styles.changed : ''}`}>
                    {changedVars.has(name) ? '● ' : ''}
                    {name}
                  </span>
                  <span className={styles.varType}>{info.type}</span>
                </div>
                <TypeInput
                  value={values[name] ?? info.value}
                  onChange={(v) => handleChange(name, v)}
                />
                {changedVars.has(name) && (
                  <div className={styles.originalValue}>was: {info.value}</div>
                )}
              </div>
            ))
          )}
        </div>

        {changedList.length > 0 && (
          <div className={styles.summary}>
            <span className={styles.summaryLabel}>You changed:</span>
            <code className={styles.summaryCode}>
              {changedList.map((v) => `${v} = ${values[v]}`).join(', ')}
            </code>
          </div>
        )}

        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onClose} disabled={isLoading}>
            Cancel
          </button>
          <button
            className={styles.replayBtn}
            onClick={handleSubmit}
            disabled={isLoading || changedList.length === 0}
          >
            {isLoading ? '⏳ Replaying...' : '🔁 Replay from Here'}
          </button>
        </div>
      </div>
    </div>
  );
}
