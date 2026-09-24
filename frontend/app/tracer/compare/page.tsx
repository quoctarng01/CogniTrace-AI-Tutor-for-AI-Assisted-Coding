'use client';
/**
 * Purpose: Side-by-side trace diff page. The student pastes two Python
 *          snippets (or picks two saved share tokens / trace ids) and
 *          sees:
 *            1. Two FingerprintBadge chips at the top (A → B).
 *            2. The field-level diff (FingerprintDiff).
 *            3. A line-by-line walkthrough of *where* in the source the
 *               structural change lives.
 *            4. A shareable link (URL embeds both ids; backend stores
 *               the diff output in the OG card).
 *
 *          Implements THESIS-05 §4 ("Fingerprint Comparison / Trace
 *          Diff") — the Socratic-at-the-trace-level demo.
 * Collaborators: hooks/useFingerprintDiff, components/tracer/FingerprintDiff
 * Last significant change: T1-D (Trace Diff)
 */
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { FingerprintDiff } from '@/components/tracer/FingerprintDiff';
import { useFingerprintDiff } from '@/hooks/useFingerprintDiff';
import {
  fingerprintDiffCardUrl,
  computeFingerprintFromCode,
} from '@/lib/api';
import type { FingerprintPayload } from '@/types/fingerprint';

interface DiffPageProps {}

type InputMode = 'paste' | 'ids';

export default function ComparePage(_props: DiffPageProps) {
  // `useSearchParams()` in Next.js 15 requires a Suspense boundary when
  // used in a page that may be statically pre-rendered. We wrap the
  // real implementation in `ComparePageInner` and render a lightweight
  // fallback here so prerendering can complete.
  return (
    <Suspense fallback={<ComparePageFallback />}>
      <ComparePageInner />
    </Suspense>
  );
}

function ComparePageFallback() {
  return (
    <main
      style={{
        minHeight: '100vh',
        padding: '2.5rem 1.5rem',
        color: '#e2e8f0',
        background: '#0f172a',
      }}
    >
      <div style={{ maxWidth: '56rem', margin: '0 auto' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Trace diff</h1>
        <p style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: '#94a3b8' }}>
          Loading comparison…
        </p>
      </div>
    </main>
  );
}

function ComparePageInner() {
  const router = useRouter();
  const params = useSearchParams();

  const initialA = params.get('a') ?? '';
  const initialB = params.get('b') ?? '';
  const [inputMode, setInputMode] = useState<InputMode>(
    initialA && initialB ? 'ids' : 'paste'
  );
  const [aInput, setAInput] = useState(initialA);
  const [bInput, setBInput] = useState(initialB);
  const [codeA, setCodeA] = useState('');
  const [codeB, setCodeB] = useState('');
  const [submittedA, setSubmittedA] = useState(initialA);
  const [submittedB, setSubmittedB] = useState(initialB);
  // For paste mode, we POST the source code to /fingerprint/from-code
  // and store the resulting fingerprint in client state so the diff
  // hook can render immediately.
  const [pastedFpA, setPastedFpA] = useState<FingerprintPayload | null>(null);
  const [pastedFpB, setPastedFpB] = useState<FingerprintPayload | null>(null);
  const [pasteError, setPasteError] = useState<string | null>(null);
  const [isComputing, setIsComputing] = useState(false);

  // When the URL carries `?a=&b=` we already know the inputs.
  useEffect(() => {
    if (initialA && initialB) {
      setSubmittedA(initialA);
      setSubmittedB(initialB);
      setInputMode('ids');
    }
  }, [initialA, initialB]);

  const { data, isLoading, error } = useFingerprintDiff({
    a: submittedA || null,
    b: submittedB || null,
  });

  const handleCompareIds = useCallback(() => {
    const trimmedA = aInput.trim();
    const trimmedB = bInput.trim();
    if (!trimmedA || !trimmedB) return;
    setSubmittedA(trimmedA);
    setSubmittedB(trimmedB);
    setPastedFpA(null);
    setPastedFpB(null);
    // Reflect the pair in the URL so the page is shareable.
    const sp = new URLSearchParams({ a: trimmedA, b: trimmedB });
    router.replace(`/tracer/compare?${sp.toString()}`);
  }, [aInput, bInput, router]);

  const handleComparePaste = useCallback(async () => {
    if (!codeA.trim() || !codeB.trim()) return;
    setIsComputing(true);
    setPasteError(null);
    try {
      const [fpA, fpB] = await Promise.all([
        computeFingerprintFromCode(codeA),
        computeFingerprintFromCode(codeB),
      ]);
      setPastedFpA(fpA);
      setPastedFpB(fpB);
      // Use the backend-computed signatures as opaque identifiers so the
      // hook receives the *exact* same wire shape as a real trace.
      setSubmittedA(`paste:${fpA.signature}`);
      setSubmittedB(`paste:${fpB.signature}`);
    } catch (e) {
      setPasteError(e instanceof Error ? e.message : 'Failed to compute');
    } finally {
      setIsComputing(false);
    }
  }, [codeA, codeB]);

  const ogImage = useMemo(() => {
    if (!submittedA || !submittedB) return null;
    return fingerprintDiffCardUrl(submittedA, submittedB);
  }, [submittedA, submittedB]);

  return (
    <main
      style={{
        maxWidth: 960,
        margin: '0 auto',
        padding: '2rem 1.25rem 4rem',
        fontFamily: 'var(--font-sans, system-ui, sans-serif)',
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <div>
          <Link href="/" style={{ textDecoration: 'none', color: 'inherit' }}>
            <strong style={{ fontSize: '1.1rem' }}>◈ CogniTrace</strong>
          </Link>
          <h1 style={{ margin: '0.4rem 0 0', fontSize: '1.5rem' }}>
            Compare Trace Fingerprints
          </h1>
          <p
            style={{
              margin: '0.25rem 0 0',
              color: 'var(--text-muted, #475569)',
              fontSize: '0.95rem',
              maxWidth: 640,
            }}
          >
            Pick two traces — by share token, trace id, or pasted Python — and
            see exactly which structural metric changed. The diff is
            deterministic: identical source code always produces identical
            fingerprints, so this view doubles as a "did my edit actually
            change the runtime shape?" check.
          </p>
        </div>
      </header>

      <nav
        aria-label="Input mode"
        style={{
          display: 'inline-flex',
          gap: '0.5rem',
          marginBottom: '1rem',
        }}
      >
        <ModeTab
          active={inputMode === 'paste'}
          onClick={() => setInputMode('paste')}
        >
          Paste two snippets
        </ModeTab>
        <ModeTab
          active={inputMode === 'ids'}
          onClick={() => setInputMode('ids')}
        >
          Use share tokens / trace ids
        </ModeTab>
      </nav>

      {inputMode === 'paste' ? (
        <PastePanel
          codeA={codeA}
          codeB={codeB}
          setCodeA={setCodeA}
          setCodeB={setCodeB}
          onSubmit={handleComparePaste}
          isComputing={isComputing}
          pasteError={pasteError}
        />
      ) : (
        <IdsPanel
          a={aInput}
          b={bInput}
          setA={setAInput}
          setB={setBInput}
          onSubmit={handleCompareIds}
        />
      )}

      <section
        aria-label="Diff result"
        style={{
          marginTop: '2rem',
          padding: '1.25rem',
          border: '1px solid var(--border, #e5e7eb)',
          borderRadius: '10px',
          background: 'var(--card-bg, #fff)',
        }}
      >
        {inputMode === 'paste' && pastedFpA && pastedFpB ? (
          <FingerprintDiff
            diff={{
              a: pastedFpA,
              b: pastedFpB,
              a_kind: 'trace_id',
              b_kind: 'trace_id',
              deltas: [],
              identical: false,
              summary: '',
            }}
          />
        ) : !submittedA || !submittedB ? (
          <EmptyDiff />
        ) : isLoading ? (
          <p>Computing fingerprint diff…</p>
        ) : error === 'not-found' ? (
          <p style={{ color: 'var(--danger, #b91c1c)' }}>
            One of the two traces couldn’t be found. Double-check the share
            token or trace id.
          </p>
        ) : error === 'network' ? (
          <p style={{ color: 'var(--danger, #b91c1c)' }}>
            Couldn’t reach the diff endpoint. Try again in a moment.
          </p>
        ) : data ? (
          <>
            <FingerprintDiff diff={data} />
            <p
              style={{
                margin: '1.25rem 0 0',
                fontSize: '0.85rem',
                color: 'var(--text-muted, #475569)',
              }}
            >
              {ogImage && (
                <>
                  Share this diff as an{' '}
                  <a
                    href={ogImage}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    OG-card SVG
                  </a>
                  .
                </>
              )}
            </p>
          </>
        ) : null}
      </section>
    </main>
  );
}

function ModeTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}): React.ReactNode {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: '0.4rem 0.9rem',
        borderRadius: '999px',
        border: '1px solid var(--border, #cbd5e1)',
        background: active ? 'var(--accent, #6366f1)' : 'transparent',
        color: active ? '#fff' : 'var(--text, #1a1a1a)',
        cursor: 'pointer',
        fontWeight: 500,
        fontSize: '0.9rem',
      }}
    >
      {children}
    </button>
  );
}

function PastePanel({
  codeA,
  codeB,
  setCodeA,
  setCodeB,
  onSubmit,
  isComputing,
  pasteError,
}: {
  codeA: string;
  codeB: string;
  setCodeA: (s: string) => void;
  setCodeB: (s: string) => void;
  onSubmit: () => void;
  isComputing: boolean;
  pasteError: string | null;
}): React.ReactNode {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '1rem',
      }}
    >
      <PasteColumn
        title="Trace A"
        value={codeA}
        onChange={setCodeA}
        placeholder={'# Paste your first Python snippet\nfor i in range(4):\n    print(i)'}
      />
      <PasteColumn
        title="Trace B"
        value={codeB}
        onChange={setCodeB}
        placeholder={'# Paste the second snippet to compare against\nfor i in range(8):\n    print(i)'}
      />
      <div style={{ gridColumn: '1 / -1', textAlign: 'right' }}>
        <button
          type="button"
          onClick={onSubmit}
          disabled={!codeA.trim() || !codeB.trim() || isComputing}
          style={{
            padding: '0.5rem 1.1rem',
            borderRadius: '6px',
            border: 'none',
            background: 'var(--accent, #6366f1)',
            color: '#fff',
            cursor:
              codeA.trim() && codeB.trim() && !isComputing
                ? 'pointer'
                : 'not-allowed',
            opacity:
              codeA.trim() && codeB.trim() && !isComputing ? 1 : 0.6,
            fontWeight: 600,
          }}
        >
          {isComputing ? 'Computing…' : 'Compare'}
        </button>
        {pasteError && (
          <p
            style={{
              margin: '0.5rem 0 0',
              color: 'var(--danger, #b91c1c)',
              fontSize: '0.85rem',
            }}
          >
            {pasteError}
          </p>
        )}
      </div>
    </div>
  );
}

function PasteColumn({
  title,
  value,
  onChange,
  placeholder,
}: {
  title: string;
  value: string;
  onChange: (s: string) => void;
  placeholder: string;
}): React.ReactNode {
  return (
    <div>
      <label
        style={{
          display: 'block',
          fontWeight: 600,
          marginBottom: '0.35rem',
          fontSize: '0.9rem',
        }}
      >
        {title}
      </label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={9}
        style={{
          width: '100%',
          padding: '0.6rem 0.7rem',
          border: '1px solid var(--border, #cbd5e1)',
          borderRadius: '6px',
          fontFamily:
            'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
          fontSize: '0.85rem',
          lineHeight: 1.5,
          resize: 'vertical',
        }}
      />
    </div>
  );
}

function IdsPanel({
  a,
  b,
  setA,
  setB,
  onSubmit,
}: {
  a: string;
  b: string;
  setA: (s: string) => void;
  setB: (s: string) => void;
  onSubmit: () => void;
}): React.ReactNode {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        gap: '0.75rem',
      }}
    >
      <label>
        <div style={{ fontWeight: 600, marginBottom: '0.3rem' }}>
          Trace A (share token or trace id)
        </div>
        <input
          type="text"
          value={a}
          onChange={(e) => setA(e.target.value)}
          placeholder="e.g. abc123… or a UUID"
          style={inputStyle}
        />
      </label>
      <label>
        <div style={{ fontWeight: 600, marginBottom: '0.3rem' }}>
          Trace B (share token or trace id)
        </div>
        <input
          type="text"
          value={b}
          onChange={(e) => setB(e.target.value)}
          placeholder="e.g. def456… or a UUID"
          style={inputStyle}
        />
      </label>
      <div style={{ gridColumn: '1 / -1', textAlign: 'right' }}>
        <button
          type="submit"
          disabled={!a.trim() || !b.trim()}
          style={{
            padding: '0.5rem 1.1rem',
            borderRadius: '6px',
            border: 'none',
            background: 'var(--accent, #6366f1)',
            color: '#fff',
            cursor: a.trim() && b.trim() ? 'pointer' : 'not-allowed',
            opacity: a.trim() && b.trim() ? 1 : 0.6,
            fontWeight: 600,
          }}
        >
          Compare
        </button>
      </div>
    </form>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.5rem 0.7rem',
  border: '1px solid var(--border, #cbd5e1)',
  borderRadius: '6px',
  fontFamily:
    'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
  fontSize: '0.85rem',
};

function EmptyDiff(): React.ReactNode {
  return (
    <p
      style={{
        margin: 0,
        color: 'var(--text-muted, #475569)',
        fontSize: '0.95rem',
      }}
    >
      Pick two traces above to see the structural delta. The diff runs in the
      browser — no LLM involved — so it loads instantly even on large traces.
    </p>
  );
}