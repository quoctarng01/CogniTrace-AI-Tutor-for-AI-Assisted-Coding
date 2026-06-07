import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect } from 'vitest';
import { ExplanationPanel } from '@/components/llm/ExplanationPanel';

// Mock the hook
vi.mock('@/hooks/useStreamingExplanation', () => ({
  useStreamingExplanation: () => ({
    text: 'This is a test explanation.',
    state: 'done',
    error: null,
    provider: 'github_models',
    start: vi.fn(),
    stop: vi.fn(),
    retry: vi.fn(),
  }),
}));

// Mock fetch
global.fetch = vi.fn() as ReturnType<typeof vi.fn>;

describe('ExplanationPanel', () => {
  it('shows rating widget after streaming completes', () => {
    render(<ExplanationPanel code="x = 1" lineNumber={1} lineContent="x = 1" locals={{}} />);

    // Rating widget should appear when state === 'done'
    expect(screen.getByText(/Was this explanation helpful?/)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Rate \d stars/ })).toHaveLength(5);
  });

  it('calls submitRating when star is clicked', async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve({ status: 'ok' }) });
    global.fetch = mockFetch;

    render(<ExplanationPanel code="x = 1" lineNumber={1} lineContent="x = 1" locals={{}} />);

    const stars = screen.getAllByRole('button', { name: /Rate \d stars/ });
    const fourthStar = stars[3];
    if (fourthStar) fireEvent.click(fourthStar);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/ratings',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"rating":4'),
        })
      );
    });
  });

  it('shows confirmation after rating', () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve({ status: 'ok' }) });
    global.fetch = mockFetch;

    render(<ExplanationPanel code="x = 1" lineNumber={1} lineContent="x = 1" locals={{}} />);

    const stars = screen.getAllByRole('button', { name: /Rate \d stars/ });
    const fifthStar = stars[4];
    if (fifthStar) fireEvent.click(fifthStar);

    expect(screen.getByText('Thanks for your feedback!')).toBeInTheDocument();
  });
});
