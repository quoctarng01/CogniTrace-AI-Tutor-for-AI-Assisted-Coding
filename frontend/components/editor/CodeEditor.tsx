'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import dynamic from 'next/dynamic';
import styles from './CodeEditor.module.css';
import { CodeEditorSkeleton } from './CodeEditorSkeleton';
import type { Annotation } from '@/types/annotation';

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false });

interface CodeEditorProps {
  code: string;
  onChange?: (value: string) => void;
  onLineClick?: (lineNumber: number) => void;
  onAnnotationClick?: (annotation: Annotation, lineNumber: number) => void;
  currentLine?: number;
  annotations?: Annotation[];
  readOnly?: boolean;
  height?: string;
}

export function CodeEditor({
  code,
  onChange,
  onLineClick,
  onAnnotationClick,
  currentLine,
  annotations = [],
  readOnly = false,
  height = '100%',
}: CodeEditorProps) {
  const editorRef = useRef<unknown>(null);
  const monacoRef = useRef<unknown>(null);
  const decorationsRef = useRef<{ clear: () => void } | null>(null);
  const isMountedRef = useRef(true);
  const [isEditorReady, setIsEditorReady] = useState(false);

  // ── Apply annotation markers (squiggles + hover tooltip) ────────
  useEffect(() => {
    if (!isEditorReady) return;

    const editor = editorRef.current as {
      getModel?: () => { setModelMarkers: (owner: string, markers: unknown[]) => void } | null;
    } | null;
    const monaco = monacoRef.current as {
      editor?: { setModelMarkers: (model: unknown, owner: string, markers: unknown[]) => void };
    } | null;

    if (!editor?.getModel) return;

    const severityToMonaco = {
      high: 'error' as const,
      medium: 'warning' as const,
      low: 'hint' as const,
    };

    const markers = annotations.map(ann => ({
      severity: severityToMonaco[ann.severity] ?? 'hint',
      startLineNumber: ann.line,
      startColumn: 1,
      endLineNumber: ann.line,
      endColumn: Number.MAX_SAFE_INTEGER,
      message: `[${ann.pattern_id}] ${ann.message}\n\nSuggestion: ${ann.suggestion}`,
      source: 'CodeScope',
    }));

    const model = editor.getModel();
    if (!model) return;

    // Monaco API: monaco.editor.setModelMarkers(model, owner, markers)
    if (monaco?.editor?.setModelMarkers) {
      monaco.editor.setModelMarkers(model, 'codescope-analyzer', markers);
    } else {
      // Fallback: setModelMarkers on the model itself (older Monaco API)
      (model as { setModelMarkers: (owner: string, markers: unknown[]) => void }).setModelMarkers(
        'codescope-analyzer',
        markers
      );
    }

    return () => {
      if (monaco?.editor?.setModelMarkers) {
        monaco.editor.setModelMarkers(model, 'codescope-analyzer', []);
      } else {
        (model as { setModelMarkers: (owner: string, markers: unknown[]) => void }).setModelMarkers(
          'codescope-analyzer',
          []
        );
      }
    };
  }, [annotations, isEditorReady]);

  const handleMount = useCallback(
    (editor: unknown, monaco: unknown) => {
      if (!isMountedRef.current) return;
      editorRef.current = editor;
      monacoRef.current = monaco;
      setIsEditorReady(true);

      // Add line click handler
      const monacoEditor = editor as {
        onMouseDown: (
          callback: (e: { target: { position?: { lineNumber?: number } } }) => void
        ) => void;
      };
      if (onLineClick && monacoEditor?.onMouseDown) {
        monacoEditor.onMouseDown(e => {
          if (e.target?.position?.lineNumber) {
            onLineClick(e.target.position.lineNumber);
          }
        });
      }
    },
    [onLineClick]
  );

  // Update line decorations whenever currentLine changes
  useEffect(() => {
    // Wait for editor to be ready before applying decorations
    if (!isEditorReady) return;

    const editor = editorRef.current as {
      createDecorationsCollection: (d: unknown[]) => { clear: () => void };
      getDomNode?: () => HTMLElement | null;
    } | null;
    const monaco = monacoRef.current as {
      Range: new (ln: number, sc: number, le: number, ec: number) => unknown;
    } | null;

    if (!editor || !monaco || !isMountedRef.current) return;

    // Clear old decorations
    if (decorationsRef.current) {
      decorationsRef.current.clear();
      decorationsRef.current = null;
    }

    if (currentLine === undefined || currentLine < 1) return;

    // Apply new decoration with a small delay to ensure editor is ready
    const timeoutId = setTimeout(() => {
      if (!isMountedRef.current || !editorRef.current || !monacoRef.current) return;
      try {
        decorationsRef.current = (editorRef.current as typeof editor).createDecorationsCollection([
          {
            range: new (monacoRef.current as typeof monaco).Range(currentLine, 1, currentLine, 1),
            options: {
              isWholeLine: true,
              className: styles.currentLineHighlight,
              linesDecorationsClassName: styles.currentLineBorder,
            },
          },
        ]);
      } catch {
        // Editor may be disposing, ignore
      }
    }, 50);

    return () => clearTimeout(timeoutId);
  }, [currentLine, isEditorReady]);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      setIsEditorReady(false);
      if (decorationsRef.current) {
        decorationsRef.current.clear();
        decorationsRef.current = null;
      }
      editorRef.current = null;
      monacoRef.current = null;
    };
  }, []);

  return (
    <div className={styles.editorWrapper}>
      <MonacoEditor
        height={height}
        language="python"
        theme="vs-dark"
        value={code}
        onChange={value => onChange?.(value ?? '')}
        options={{
          readOnly,
          minimap: { enabled: false },
          lineNumbers: 'on',
          fontSize: 14,
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
          fontLigatures: true,
          scrollBeyondLastLine: false,
          renderLineHighlight: 'none',
          overviewRulerBorder: false,
          hideCursorInOverviewRuler: true,
          scrollbar: {
            verticalScrollbarSize: 6,
            horizontalScrollbarSize: 6,
          },
          padding: { top: 16, bottom: 16 },
          lineHeight: 24,
          cursorBlinking: 'smooth',
          smoothScrolling: true,
          wordWrap: 'on',
          automaticLayout: true,
          tabSize: 4,
          insertSpaces: true,
          folding: false,
          glyphMargin: true,
          contextmenu: !readOnly,
          renderWhitespace: 'none',
        }}
        loading={<CodeEditorSkeleton />}
        onMount={handleMount}
      />
    </div>
  );
}
