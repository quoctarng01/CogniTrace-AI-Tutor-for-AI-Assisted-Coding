import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { FingerprintPayload } from '@/types/fingerprint';

// ── Mocks ──────────────────────────────────────────────────────────

const mockUseParams = vi.fn();
vi.mock('next/navigation', () => ({
  useParams: () => mockUseParams(),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}));

const mockFetchByShareToken = vi.fn();
vi.mock('@/lib/api', () => ({
  fetchFingerprintByShareToken: (...args: unknown[]) => mockFetchByShareToken(...args),
  fingerprintCardUrl: (t: string) => `https://api.example.com/fingerprint/${t}/card.svg`,
}));

// Import after mocks so the page picks them up.
import FingerprintSharePage from '@/app/fingerprint/[share_token]/page';

const sampleFp: FingerprintPayload = {
  branches: 2,
  recursion_depth: 1,
  exception_types: ['ZeroDivisionError'],
  loop_iterations: 2,
  total_steps: 12,
  conceptual_complexity: '🟡',
  total_duration_ms: 47,
  ast_metrics: {},
  compact: '◆B2-R1-E1-LO2-EX12-CC🟡-T47ms',
  short: '◆B2·R1·E1·LO2·T47ms',
  signature: 'cafe0000',
};

// ── Tests ──────────────────────────────────────────────────────────

describe('<FingerprintSharePage>', () => {
  beforeEach(() => {
    mockUseParams.mockReset();
    mockFetchByShareToken.mockReset();
    mockUseParams.mockReturnValue({ share_token: 'tok-123' });
  });

  it('renders a loading state initially', () => {
    mockFetchByShareToken.mockReturnValue(new Promise(() => {})); // never resolves
    render(<FingerprintSharePage />);
    expect(screen.getByText(/Loading fingerprint/i)).toBeInTheDocument();
  });

  it('renders the fingerprint hero on success', async () => {
    mockFetchByShareToken.mockResolvedValue(sampleFp);
    render(<FingerprintSharePage />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /trace fingerprint/i })).toBeInTheDocument();
    });
    expect(screen.getByText('◆B2-R1-E1-LO2-EX12-CC🟡-T47ms')).toBeInTheDocument();
    // The exception name appears in the Exceptions metric card.
    expect(screen.getByText('ZeroDivisionError')).toBeInTheDocument();
    // The "Medium complexity" copy.
    expect(screen.getByText(/Medium complexity\./)).toBeInTheDocument();
  });

  it('renders the not-found panel when FINGERPRINT_NOT_FOUND is thrown', async () => {
    mockFetchByShareToken.mockRejectedValue(new Error('FINGERPRINT_NOT_FOUND'));
    render(<FingerprintSharePage />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /fingerprint not found/i })).toBeInTheDocument();
    });
  });

  it('renders the network-error panel for any other error', async () => {
    mockFetchByShareToken.mockRejectedValue(new Error('network down'));
    render(<FingerprintSharePage />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /couldn.t load fingerprint/i })).toBeInTheDocument();
    });
  });

  it('links to the full trace view from the hero', async () => {
    mockFetchByShareToken.mockResolvedValue(sampleFp);
    render(<FingerprintSharePage />);
    await waitFor(() => {
      expect(screen.getByText('◆B2-R1-E1-LO2-EX12-CC🟡-T47ms')).toBeInTheDocument();
    });
    const link = screen.getByRole('link', { name: /open full trace/i });
    expect(link).toHaveAttribute('href', '/trace/tok-123');
  });

  it('links to the OG card SVG using fingerprintCardUrl', async () => {
    mockFetchByShareToken.mockResolvedValue(sampleFp);
    render(<FingerprintSharePage />);
    await waitFor(() => {
      expect(screen.getByText('◆B2-R1-E1-LO2-EX12-CC🟡-T47ms')).toBeInTheDocument();
    });
    const ogLink = screen.getByRole('link', { name: /open og card svg/i });
    expect(ogLink).toHaveAttribute('href', 'https://api.example.com/fingerprint/tok-123/card.svg');
  });

  it('passes the share token from useParams to the fetcher', async () => {
    mockUseParams.mockReturnValue({ share_token: 'tok-xyz' });
    mockFetchByShareToken.mockResolvedValue(sampleFp);
    render(<FingerprintSharePage />);
    await waitFor(() => {
      expect(mockFetchByShareToken).toHaveBeenCalledWith('tok-xyz');
    });
  });
});
