'use client';
/**
 * /tracer/ab — the thesis-defense "wow" demo page.
 *
 * Workstream 11 (THESIS-W1-RESULTS.md §3.3). Isolated from /tracer
 * so we never break the production demo. Pre-loads the B06 bare-except
 * snippet (largest effect-size cell in the W1 pilot, d = -2.31).
 *
 * Flow:
 *   1. B06 snippet pre-loaded in the editor.
 *   2. Click "▶ Trace" — POST /api/traces/run. Steps + variables populate.
 *   3. Click any line in the code → "Explain this line in A/B mode" button activates.
 *   4. Click the button → fires /api/llm/ab.
 *   5. Watch both streams fill side-by-side; verdict card renders below.
 */

import { useCallback, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useTraceRunner } from '@/hooks/useTraceRunner';
import { VariablePanel } from '@/components/tracer/VariablePanel';
import { AblationArena } from '@/components/ab/AblationArena';
import { api, runTrace } from '@/lib/api';
import type { TraceResult } from '@/types/trace';
import styles from './ab.module.css';

const CodeEditor = dynamic(
  () => import('@/components/editor/CodeEditor').then((m) => m.CodeEditor),
  { ssr: false, loading: () => <div className={styles.editorLoading}>Loading editor…</div> },
);

// B06 — bare-except. W1 pilot strongest cell: d = -2.31 (grounded beats both
// trace-only and control by a wide margin on this concept).
const B06_SNIPPET = `def safe_divide(a, b):
    try:
        result = a / b
    except:
        print("Something went wrong")
        return None
    return result

# Caller has no idea what went wrong.
print(safe_divide(10, 0))   # ZeroDivisionError, silently swallowed
print(safe_divide(10, "x")) # TypeError, also swallowed
`;

function extractConceptTags(code: string): string[] {
  const tags: string[] = [];
  if (/def\s+\w+\(/.test(code)) tags.push('FUNCTION');
  if (/for\s/.test(code)) tags.push('LOOP');
  if (/while\s/.test(code)) tags.push('LOOP');
  if (/if\s/.test(code)) tags.push('CONDITIONAL');
  if (/class\s/.test(code)) tags.push('CLASS');
  if (/try\s|except\s/.test(code)) tags.push('EXCEPTION');
  return tags.slice(0, 4);
}

export default function TracerAbPage() {
  const [code, setCode] = useState(B06_SNIPPET);
  const [selectedLine, setSelectedLine] = useState<number | null>(null);
  const [hoveredVariable, setHoveredVariable] = useState<string | null>(null);
  const [runId, setRunId] = useState(0);

  // Run the trace once on mount via runId
  const { result: traceResult, isLoading, error, run } = useTraceRunner({
    extractConceptTags,
  });

  // Run trace on first render
  useMemo(() => {
    void run(code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const steps = traceResult?.steps ?? [];

  // Find the currently-selected step's variables (or default to step 0)
  const currentStep = useMemo(() => {
    if (selectedLine === null) return steps[0] ?? null;
    return steps.find((s) => s.line_number === selectedLine) ?? steps[0] ?? null;
  }, [selectedLine, steps]);

  const lineContent = useMemo(() => {
    if (selectedLine === null) return '';
    return code.split('\n')[selectedLine - 1]?.trim() ?? '';
  }, [selectedLine, code]);

  const onRunAb = useCallback(() => {
    setRunId((prev) => prev + 1);
  }, []);

  const onTraceAgain = useCallback(async () => {
    await run(code);
  }, [code, run]);

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <div className={styles.brand}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CogniTrace · A/B Demo</span>
        </div>
        <div className={styles.tagline}>
          Thesis Defense Demo · Grounded vs Blind · <code>/api/llm/ab</code>
        </div>
      </header>

      <main className={styles.main}>
        <section className={styles.editorPanel}>
          <div className={styles.editorToolbar}>
            <button
              type="button"
              className={styles.traceBtn}
              onClick={onTraceAgain}
              disabled={isLoading || !code.trim()}
            >
              {isLoading ? '⏳ Tracing…' : '▶ Re-trace'}
            </button>
            <span className={styles.editorHint}>
              Click any line below to select it for the A/B comparison.
            </span>
          </div>
          <CodeEditor
            code={code}
            onChange={setCode}
            onLineClick={(ln) => setSelectedLine(ln)}
            currentLine={selectedLine ?? undefined}
          />
        </section>

        <section className={styles.rightPanel}>
          <div className={styles.variablePanel}>
            <VariablePanel
              variables={currentStep?.variables ?? {}}
              branches={currentStep?.branches_taken ?? {}}
              isLoading={isLoading}
            />
          </div>

          <div className={styles.arenaPanel}>
            <AblationArena
              code={code}
              lineNumber={selectedLine ?? 1}
              lineContent={lineContent || code.split('\n')[0]?.trim() || ''}
              locals={currentStep?.variables ?? {}}
              runId={runId}
              hoveredVariable={hoveredVariable}
            />
          </div>

          <div className={styles.runRow}>
            <button
              type="button"
              className={styles.runBtn}
              onClick={onRunAb}
              disabled={!traceResult || isLoading}
              title={!traceResult ? 'Run the trace first' : 'Compare grounded vs blind explanations'}
            >
              ⚡ Run A/B Comparison
            </button>
            {error && <span className={styles.error}>{error}</span>}
          </div>
        </section>
      </main>
    </div>
  );
}
