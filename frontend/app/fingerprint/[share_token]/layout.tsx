// frontend/app/fingerprint/[share_token]/layout.tsx
/**
 * Purpose: Server-component layout that emits the Open Graph / Twitter card
 *          metadata for the fingerprint share page. The page itself is a
 *          'use client' component (it does authenticated fetches), so this
 *          sibling layout is the canonical Next.js place to define the
 *          metadata used by social-card crawlers.
 *
 *          The OG image is the SVG card served by the backend at
 *          `/fingerprint/{share_token}/card.svg` — anonymous callers see
 *          public traces only, which is exactly what crawlers do.
 *
 * Collaborators: backend/app/routers/fingerprint.py (card.svg endpoint)
 * Last significant change: Workstream 12 (Trace Fingerprint)
 */
import type { Metadata } from 'next';
import type { ReactNode } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? 'https://code-scope-ai-tutor-for-ai-assisted.vercel.app';

export async function generateMetadata({
  params,
}: {
  params: { share_token: string };
}): Promise<Metadata> {
  const shareToken = params.share_token;
  const ogImage = `${API_BASE}/fingerprint/${shareToken}/card.svg`;
  const canonical = `${SITE_URL}/fingerprint/${shareToken}`;

  return {
    title: 'Trace Fingerprint · CogniTrace',
    description:
      'Deterministic trace classification — one-line signature for every saved trace. AST-driven, no LLM, shareable.',
    alternates: { canonical },
    openGraph: {
      type: 'website',
      url: canonical,
      title: 'Trace Fingerprint · CogniTrace',
      description:
        'Every CogniTrace trace classified in one line: branches, recursion, exceptions, complexity traffic light.',
      images: [
        {
          url: ogImage,
          width: 1200,
          height: 630,
          alt: 'CogniTrace trace fingerprint card',
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title: 'Trace Fingerprint · CogniTrace',
      description:
        'Deterministic AST classification for every saved trace — shareable one-line signature + SVG card.',
      images: [ogImage],
    },
  };
}

export default function FingerprintShareLayout({
  children,
}: {
  children: ReactNode;
}) {
  return <>{children}</>;
}
