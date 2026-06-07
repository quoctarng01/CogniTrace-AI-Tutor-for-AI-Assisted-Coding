import type { Metadata } from 'next';
import { Inter, Lora, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { SupabaseListener } from './supabase-provider';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
});

const lora = Lora({
  subsets: ['latin'],
  variable: '--font-serif',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'CogniTrace - Understand AI-generated Python code',
  description: 'CogniTrace traces how Cursor, Copilot, and ChatGPT write Python — variable by variable, branch by branch — then schedules spaced reviews so you actually remember what you shipped.',
  icons: {
    icon: '/favicon.svg',
  },
  alternates: {
    canonical: 'https://code-scope-ai-tutor-for-ai-assisted.vercel.app',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="canonical" href="https://code-scope-ai-tutor-for-ai-assisted.vercel.app" />
        <meta name="robots" content="index, follow" />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('theme') || 'light';
                  if (theme === 'dark') {
                    document.documentElement.classList.add('dark');
                    document.body.classList.add('dark');
                  } else {
                    document.documentElement.classList.remove('dark');
                    document.body.classList.remove('dark');
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebApplication",
              "name": "CogniTrace",
              "description": "Understand AI-generated Python code through step-by-step tracing and spaced repetition.",
              "url": "https://code-scope-ai-tutor-for-ai-assisted.vercel.app",
              "applicationCategory": "EducationApplication",
              "operatingSystem": "Any",
            }),
          }}
        />
      </head>
      <body className={`${inter.variable} ${lora.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
        <SupabaseListener />
        {children}
      </body>
    </html>
  );
}
