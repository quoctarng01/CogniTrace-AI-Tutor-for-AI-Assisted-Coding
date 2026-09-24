// frontend/app/fingerprint/[share_token]/page.tsx
'use client';
/**
 * Purpose: Human-facing share page for a single trace fingerprint. Loads via
 *          `/api/fingerprint/{share_token}` (which is auth-aware: public traces
 *          are reachable anonymously, private traces require the owner token).
 *          The OG / Twitter card image lives at `/fingerprint/{token}/card.svg`
 *          and is wired through the matching `opengraph-image.tsx` route.
 * Collaborators: api.ts (fetchFingerprintByShareToken), fingerprint.ts (types)
 * Last significant change: Workstream 12 (Trace Fingerprint)
 */


import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  fetchFingerprintByShareToken,
  fingerprintCardUrl,
} from '@/lib/api';
import { complexityBucket } from '@/types/fingerprint';
import type { FingerprintPayload } from '@/types/fingerprint';
import styles from './share.module.css';

export default function FingerprintSharePage() {
  const params = useParams();
  const shareToken = params.share_token as string;

  const [fp, setFp] = useState<FingerprintPayload | null>(null);
  const [error, setError] = useState<'not-found' | 'network' | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    fetchFingerprintByShareToken(shareToken)
      .then((payload) => {
        if (!cancelled) setFp(payload);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : String(e);
        if (msg === 'FINGERPRINT_NOT_FOUND') setError('not-found');
        else setError('network');
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [shareToken]);

  const ogImage = fingerprintCardUrl(shareToken);

  return (
    <main className={styles.page}>
      <header className={styles.topBar}>
        <Link href="/" className={styles.brand}>
          <span className={styles.brandIcon}>◆</span>
          <span>CogniTrace</span>
        </Link>
      </header>

      <section className={styles.main}>
        {isLoading && (
          <div className={styles.loadingShell}>Loading fingerprint…</div>
        )}

        {error === 'not-found' && (
          <div className={styles.errorPanel}>
            <h1>Fingerprint not found</h1>
            <p>
              This share link may have expired, been revoked, or never existed.
            </p>
            <Link href="/" className={styles.cta}>
              Back to CogniTrace
            </Link>
          </div>
        )}

        {error === 'network' && (
          <div className={styles.errorPanel}>
            <h1>Couldn’t load fingerprint</h1>
            <p>
              We hit a server error fetching this fingerprint. Please try
              again in a moment.
            </p>
            <Link href="/" className={`${styles.cta} ${styles.ctaGhost}`}>
              Back to CogniTrace
            </Link>
          </div>
        )}

        {fp && !error && <FingerprintHero fp={fp} shareToken={shareToken} ogImage={ogImage} />}
      </section>

      <footer className={styles.footer}>
        Deterministic trace classification ·{' '}
        <Link href="/" style={{ color: 'inherit' }}>
          CogniTrace
        </Link>
      </footer>
    </main>
  );
}

interface HeroProps {
  fp: FingerprintPayload;
  shareToken: string;
  ogImage: string;
}

function FingerprintHero({ fp, shareToken, ogImage }: HeroProps) {
  const bucket = complexityBucket(fp.conceptual_complexity);
  const bucketLabel =
    bucket === 'red' ? 'High complexity' : bucket === 'yellow' ? 'Medium complexity' : 'Low complexity';
  const complexityExplain =
    bucket === 'red'
      ? 'This trace shows multiple branches, exceptions, or recursion — spend a moment walking through it before sharing.'
      : bucket === 'yellow'
      ? 'A few decisions in this trace — review the branches before moving on.'
      : 'Linear trace, mostly straightforward control flow.';

  return (
    <article className={styles.heroCard}>
      <h1 className={styles.title}>Trace Fingerprint</h1>
      <p className={styles.subtitle}>
        Every CogniTrace trace is classified deterministically by an AST
        walker — no LLM. The 8-letter signature below is the entire trace
        reduced to one line.
      </p>

      <div className={styles.fingerprintBlock}>
        <div className={styles.fingerprintSignature}>{fp.compact}</div>
        <div className={styles.fingerprintMeta}>
          SHA-1 short: <code>{fp.signature}</code> · OG form: <code>{fp.short}</code>
        </div>
      </div>

      <div className={styles.metricGrid}>
        <Metric label="Branches" value={fp.branches} hint="control-flow decisions" />
        <Metric label="Recursion" value={fp.recursion_depth} hint="recursive calls" />
        <Metric label="Loops" value={fp.loop_iterations} hint="iteration steps" />
        <Metric label="Steps" value={fp.total_steps} hint="executed opcodes" />
        <Metric
          label="Duration"
          value={`${Math.round(fp.total_duration_ms)}ms`}
          hint="wall-clock"
        />
        <Metric
          label="Exceptions"
          value={fp.exception_types.length}
          hint={fp.exception_types.join(', ') || 'none'}
        />
      </div>

      <p className={styles.subtitle}>
        <strong>{bucketLabel}.</strong> {complexityExplain}
      </p>

      <div className={styles.actions}>
        <Link
          href={`/trace/${shareToken}`}
          className={styles.cta}
          prefetch={false}
        >
          Open full trace →
        </Link>
        <a
          href={ogImage}
          target="_blank"
          rel="noopener noreferrer"
          className={`${styles.cta} ${styles.ctaGhost}`}
        >
          Open OG card SVG
        </a>
      </div>
    </article>
  );
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | string;
  hint?: string;
}) {
  return (
    <div className={styles.metricCard}>
      <span className={styles.metricLabel}>{label}</span>
      <span className={styles.metricValue}>{value}</span>
      {hint && <span className={styles.metricHint}>{hint}</span>}
    </div>
  );
}
