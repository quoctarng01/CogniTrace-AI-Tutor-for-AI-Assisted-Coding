import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FingerprintBadge } from '@/components/tracer/FingerprintBadge';
import type { FingerprintPayload } from '@/types/fingerprint';

// ── Fixtures ───────────────────────────────────────────────────────

const baseFp: FingerprintPayload = {
  branches: 2,
  recursion_depth: 0,
  exception_types: [],
  loop_iterations: 2,
  total_steps: 12,
  conceptual_complexity: '🟢',
  total_duration_ms: 47,
  ast_metrics: {},
  compact: '◆B2-R0-E0-LO2-EX12-CC🟢-T47ms',
  short: '◆B2·R0·E0·LO2·T47ms',
  signature: 'abcd1234',
};

const yellowFp: FingerprintPayload = { ...baseFp, conceptual_complexity: '🟡', compact: '◆B2-R0-E0-LO2-EX12-CC🟡-T47ms' };
const redFp: FingerprintPayload = { ...baseFp, conceptual_complexity: '🔴', compact: '◆B2-R0-E0-LO2-EX12-CC🔴-T47ms' };

// ── Tests ──────────────────────────────────────────────────────────

describe('<FingerprintBadge>', () => {
  it('renders the compact signature as the visible text', () => {
    render(<FingerprintBadge fingerprint={baseFp} />);
    expect(screen.getByText('◆B2-R0-E0-LO2-EX12-CC🟢-T47ms')).toBeInTheDocument();
  });

  it('uses an accessible label that includes the bucket name', () => {
    render(<FingerprintBadge fingerprint={yellowFp} />);
    expect(screen.getByLabelText(/yellow complexity/i)).toBeInTheDocument();
  });

  it('labels red as red-bucket complexity', () => {
    render(<FingerprintBadge fingerprint={redFp} />);
    expect(screen.getByLabelText(/red complexity/i)).toBeInTheDocument();
  });

  it('labels green as green-bucket complexity', () => {
    render(<FingerprintBadge fingerprint={baseFp} />);
    expect(screen.getByLabelText(/green complexity/i)).toBeInTheDocument();
  });

  it('renders a span by default (not a button)', () => {
    render(<FingerprintBadge fingerprint={baseFp} />);
    expect(screen.getByLabelText(/green complexity/i).tagName).toBe('SPAN');
  });

  it('renders a button when onClick is provided', () => {
    const onClick = vi.fn();
    render(<FingerprintBadge fingerprint={baseFp} onClick={onClick} />);
    const el = screen.getByLabelText(/green complexity/i);
    expect(el.tagName).toBe('BUTTON');
  });

  it('invokes onClick when the button is clicked', () => {
    const onClick = vi.fn();
    render(<FingerprintBadge fingerprint={baseFp} onClick={onClick} />);
    fireEvent.click(screen.getByLabelText(/green complexity/i));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('shows metric subline in detailed mode', () => {
    render(<FingerprintBadge fingerprint={baseFp} detailed />);
    // The compact signature appears in <strong>, the metric subline in a muted span.
    // Substring matches must use getAllByText for tokens shared by both.
    expect(screen.getAllByText(/2 branches/)).toHaveLength(1);
    expect(screen.getAllByText(/0 recursive/)).toHaveLength(1);
    expect(screen.getAllByText(/2 loop iters/)).toHaveLength(1);
    // "47ms" lives in both lines, so use a unique combined matcher.
    expect(screen.getByText(/2 branches[\s\S]*47ms/)).toBeInTheDocument();
  });

  it('singularizes branch / loop iter when count is 1', () => {
    const oneBranch: FingerprintPayload = {
      ...baseFp,
      branches: 1,
      loop_iterations: 1,
      compact: '◆B1-R0-E0-LO1-EX12-CC🟢-T47ms',
    };
    render(<FingerprintBadge fingerprint={oneBranch} detailed />);
    expect(screen.getByText(/1 branch\b/)).toBeInTheDocument();
    expect(screen.getByText(/1 loop iter\b/)).toBeInTheDocument();
  });

  it('hides the metric subline in non-detailed mode', () => {
    render(<FingerprintBadge fingerprint={baseFp} />);
    expect(screen.queryByText(/2 branches/)).not.toBeInTheDocument();
  });

  it('honours the custom label prop', () => {
    render(<FingerprintBadge fingerprint={baseFp} label="Trace T-47 — Fibonacci" />);
    expect(screen.getByLabelText('Trace T-47 — Fibonacci')).toBeInTheDocument();
  });
});
