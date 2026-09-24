"""Auto-add 3-line JSDoc headers to frontend files missing them.

This is a one-shot script for Workstream 9 — it reads the file, infers
a short description from its directory + filename, and inserts a JSDoc
block as the first non-comment statement.

It is conservative: it never replaces existing content, and it never
adds docstrings to files that already have one (the missing-file list
is pre-computed).
"""
import os, re, sys

# Hand-curated descriptions — generic auto-inference isn't worth the
# risk of producing nonsense in the codebase README.
DESCRIPTIONS = {
    'app/layout.tsx': 'Root layout — wraps every route in the Supabase provider and applies the global theme.',
    'app/page.tsx': 'Landing page — the first thing unauthenticated visitors see.',
    'app/supabase-provider.tsx': 'Client-side Supabase context. Every page reads `useSupabase()` to get the auth client.',
    'app/auth/callback/page.tsx': 'OAuth callback handler. Completes the Supabase sign-in flow and redirects.',
    'app/auth/login/page.tsx': 'Email/password + OAuth sign-in form.',
    'app/auth/signup/page.tsx': 'New-account registration form.',
    'app/dashboard/page.tsx': 'Authenticated dashboard — streak, recent traces, spaced-repetition review queue.',
    'app/examples/loading.tsx': 'Skeleton shown while the examples index is fetching.',
    'app/examples/page.tsx': 'Browse pre-built trace examples.',
    'app/examples/[id]/loading.tsx': 'Skeleton shown while a single example loads.',
    'app/examples/[id]/page.tsx': 'Detail view for one example trace.',
    'app/pricing/page.tsx': 'Pricing page — explains free / pro limits and the upgrade flow.',
    'app/review/[card_id]/page.tsx': 'Spaced-repetition review session for a single flashcard.',
    'app/trace/[share_token]/page.tsx': 'Read-only viewer for a shared trace, reached via a share token.',
    'app/tracer/page.tsx': 'The main trace editor — code input, run, explanation streaming, share modal.',
    'components/CodeBlock.tsx': 'Syntax-highlighted code block (no editor).',
    'components/editor/CodeEditor.tsx': 'The Monaco-based code editor used in the tracer page.',
    'components/editor/CodeEditorSkeleton.tsx': 'Loading skeleton shown in place of the Monaco editor.',
    'components/llm/ExplanationPanel.tsx': 'Streams the LLM explanation token-by-token into the UI.',
    'components/tracer/AnimationControls.tsx': 'Play / pause / step controls for the trace animation.',
    'components/tracer/MemoryVisualizer.tsx': 'Heap-and-stack visual used during playback.',
    'components/tracer/TraceTreePanel.tsx': 'Tree view of the trace steps.',
    'components/tracer/TutorChallenge.tsx': 'Active-learning checkpoint prompt (branch / variable / exception prediction).',
    'components/tracer/VariablePanel.tsx': 'Side panel showing the live variable state at the current step.',
    'components/tracer/WhatIfModal.tsx': 'Modal that lets a learner fork a trace at a chosen step.',
    'components/ui/Button.tsx': 'The single button primitive — variants `primary / secondary / danger / ghost`.',
    'components/ui/Modal.tsx': 'Accessible modal wrapper used by share / save / what-if dialogs.',
    'components/ui/ThemeToggle.tsx': 'Light / dark theme toggle.',
    'lib/analytics.ts': 'Client-side analytics shim — wraps PostHog / custom events behind a stable interface.',
}


def jsdoc_block(desc: str, collaborators: str = '—', last_change: str = 'Workstream 9') -> str:
    """Return a 4-line JSDoc block (purpose, collaborators, last change)."""
    return (
        '/**\n'
        f' * Purpose: {desc}\n'
        f' * Collaborators: {collaborators}\n'
        f' * Last significant change: {last_change}\n'
        ' */\n'
    )


def add_header(path: str, desc: str) -> bool:
    """Prepend a JSDoc header to `path`. Returns True if the file was modified."""
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    # Skip if a docstring is already there
    if re.search(r'^\s*(/\*\*|//!)', src, re.MULTILINE):
        return False
    # Insert after any 'use client' / 'use server' directive
    lines = src.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.strip() in ("'use client';", '"use client";', "'use server';", '"use server";'):
            insert_at = i + 1
            break
    header = jsdoc_block(desc) + '\n'
    new_src = ''.join(lines[:insert_at]) + header + ''.join(lines[insert_at:])
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_src)
    return True


def main():
    frontend_root = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    frontend_root = os.path.abspath(frontend_root)
    n_changed = 0
    for rel, desc in DESCRIPTIONS.items():
        path = os.path.join(frontend_root, rel)
        if not os.path.exists(path):
            print(f'SKIP missing: {rel}')
            continue
        if add_header(path, desc):
            n_changed += 1
            print(f'+ {rel}')
    print(f'\nChanged {n_changed} files.')


if __name__ == '__main__':
    main()
