// frontend/components/CodeBlock.tsx
'use client';

import { useMemo } from 'react';

// Dynamically import react-syntax-highlighter to avoid SSR issues
// and reduce initial bundle size.

interface CodeBlockProps {
  code: string;
  language?: string;
}

export default function CodeBlock({ code, language = 'python' }: CodeBlockProps) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const Prism = useMemo<any>(() => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const light = require('react-syntax-highlighter/dist/esm/prism-light');
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const python = require('react-syntax-highlighter/dist/esm/languages/prism/python');
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const style = require('react-syntax-highlighter/dist/esm/styles/prism/vscDarkPlus');

    light.PrismLight.registerLanguage('python', python.default);

    // Return the PrismLight component itself as the "Prism" variable
    return light.PrismLight;
  }, []);

  return (
    <Prism
      language={language}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      style={require('react-syntax-highlighter/dist/esm/styles/prism/vscDarkPlus') as any}
      customStyle={{ margin: 0, fontSize: '0.875rem', padding: '16px' }}
    >
      {code}
    </Prism>
  );
}
