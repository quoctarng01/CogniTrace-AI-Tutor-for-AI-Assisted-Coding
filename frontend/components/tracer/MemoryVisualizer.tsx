'use client';

import React from 'react';
import styles from './MemoryVisualizer.module.css';

interface MemoryVisualizerProps {
  type: string;
  value: string;
  name: string;
}

export function MemoryVisualizer({ type, value, name }: MemoryVisualizerProps) {
  let parsedValue: any = null;
  let isCollection = ['list', 'tuple', 'set', 'dict'].includes(type.toLowerCase());

  if (isCollection) {
    try {
      let sanitized = value.trim();

      // Handle python empty set
      if (sanitized === 'set()') {
        parsedValue = [];
      } else {
        // Convert Python syntax to valid JSON
        sanitized = sanitized
          .replace(/'/g, '"')
          .replace(/True/g, 'true')
          .replace(/False/g, 'false')
          .replace(/None/g, 'null');

        // Set representation conversion: {1, 2} -> [1, 2]
        if (type.toLowerCase() === 'set' && sanitized.startsWith('{') && sanitized.endsWith('}')) {
          sanitized = '[' + sanitized.slice(1, -1) + ']';
        }
        // Tuple representation conversion: (1, 2) -> [1, 2]
        else if (
          (type.toLowerCase() === 'tuple' || type.toLowerCase() === 'list') &&
          sanitized.startsWith('(') &&
          sanitized.endsWith(')')
        ) {
          sanitized = '[' + sanitized.slice(1, -1) + ']';
        }

        parsedValue = JSON.parse(sanitized);
      }
    } catch {
      parsedValue = null;
    }
  }

  if (parsedValue === null) {
    return <code className={styles.fallbackCode}>{value}</code>;
  }

  // Visual Lists, Tuples, and Sets
  if (Array.isArray(parsedValue)) {
    return (
      <div className={styles.listContainer}>
        {parsedValue.map((item, idx) => (
          <div key={`${name}-item-${idx}`} className={styles.elementBox}>
            <span className={styles.indexLabel}>{idx}</span>
            <span className={styles.elementValue}>{String(item)}</span>
          </div>
        ))}
      </div>
    );
  }

  // Visual Dictionaries
  if (typeof parsedValue === 'object') {
    return (
      <div className={styles.dictGrid}>
        {Object.entries(parsedValue).map(([k, v]) => (
          <div key={`${name}-key-${k}`} className={styles.dictPair}>
            <span className={styles.dictKey}>{k}</span>
            <span className={styles.dictArrow}>➔</span>
            <span className={styles.dictValue}>{String(v)}</span>
          </div>
        ))}
      </div>
    );
  }

  return <code className={styles.fallbackCode}>{value}</code>;
}
