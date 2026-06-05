import type { Metadata } from 'next';
import './globals.css';
import { SupabaseListener } from './supabase-provider';

export const metadata: Metadata = {
  title: 'CodeScope - Understand AI-generated Python code',
  description: 'CodeScope traces how Cursor, Copilot, and ChatGPT write Python — variable by variable, branch by branch — then schedules spaced reviews so you actually remember what you shipped.',
  icons: {
    icon: '/favicon.svg',
  },
  alternates: {
    canonical: 'https://codescope.vercel.app',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="canonical" href="https://codescope.vercel.app" />
        <meta name="robots" content="index, follow" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebApplication",
              "name": "CodeScope",
              "description": "Understand AI-generated Python code through step-by-step tracing and spaced repetition.",
              "url": "https://codescope.vercel.app",
              "applicationCategory": "EducationApplication",
              "operatingSystem": "Any",
            }),
          }}
        />
      </head>
      <body className="dark">
        <SupabaseListener />
        {children}
      </body>
    </html>
  );
}
