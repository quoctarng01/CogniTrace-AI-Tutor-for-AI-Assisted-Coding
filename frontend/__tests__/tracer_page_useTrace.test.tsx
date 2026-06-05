import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect } from 'vitest';
import TracerPage from '@/app/tracer/page';
import { useTrace } from '@/hooks/useTrace';
import { useRouter } from 'next/navigation';

// Mock all dependencies
vi.mock('@/hooks/useTrace', () => ({
  useTrace: vi.fn(() => ({
    currentStep: 0,
    playbackState: 'idle',
    speed: 1 as const,
    currentStepData: null,
    play: vi.fn(),
    pause: vi.fn(),
    togglePlayPause: vi.fn(),
    stepForward: vi.fn(),
    stepBackward: vi.fn(),
    jumpToStep: vi.fn(),
    setSpeed: vi.fn(),
    reset: vi.fn(),
  })),
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
  })),
  usePathname: vi.fn(() => '/tracer'),
  useSearchParams: vi.fn(() => new URLSearchParams()),
}));

vi.mock('@/lib/api', () => ({
  api: {
    runTrace: vi.fn(),
    analyzeCode: vi.fn(),
  },
  saveTrace: vi.fn(),
}));

vi.mock('@/lib/supabase', () => ({
  getSupabase: vi.fn(() => ({
    auth: {
      getSession: vi.fn(),
    },
  })),
  getAuthToken: vi.fn(() => Promise.resolve(null)),
}));

vi.mock('@/components/editor/CodeEditor', () => ({
  CodeEditor: () => <div data-testid="mock-editor">Mock Editor</div>,
}));

describe('TracerPage', () => {
  it('uses useTrace hook instead of manual state', () => {
    render(<TracerPage />);
    expect(useTrace).toHaveBeenCalled();
  });

  it('passes useTrace state to AnimationControls', () => {
    render(<TracerPage />);
    expect(useTrace).toHaveBeenCalledWith(
      expect.objectContaining({
        steps: expect.any(Array),
      })
    );
  });
});
