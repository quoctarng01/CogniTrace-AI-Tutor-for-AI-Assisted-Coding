/**
 * Tests for the MasteryTrajectory SVG visualization (THESIS-05 §2).
 * Pure render tests — no fetch. The aggregator that produces the
 * data is tested on the backend (test_review_trajectory.py).
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MasteryTrajectory } from '@/components/tracer/MasteryTrajectory';
import type { MasteryTrajectory as MasteryTrajectoryData } from '@/types/trajectory';

// ── Fixtures ───────────────────────────────────────────────────────

const sample: MasteryTrajectoryData = {
  total_events: 5,
  days: 30,
  date_range: { start: '2026-01-01', end: '2026-01-10' },
  concepts: [
    {
      concept_tag: 'loop_off_by_one',
      color: '#7c3aed',
      total_reviews: 3,
      current_mastery: 0.8,
      recent_miss: false,
      points: [
        { date: '2026-01-01', mastery: 0.0, rating: 'again', repetitions: 0, interval_days: 1 },
        { date: '2026-01-05', mastery: 0.4, rating: 'good',  repetitions: 1, interval_days: 6 },
        { date: '2026-01-10', mastery: 0.8, rating: 'easy',  repetitions: 3, interval_days: 18 },
      ],
    },
    {
      concept_tag: 'mutable_default_arg',
      color: '#0891b2',
      total_reviews: 2,
      current_mastery: 0.45,
      recent_miss: true,
      points: [
        { date: '2026-01-03', mastery: 0.4, rating: 'good', repetitions: 1, interval_days: 6 },
        { date: '2026-01-08', mastery: 0.45, rating: 'hard', repetitions: 1, interval_days: 3 },
      ],
    },
  ],
};

// ── Tests ─────────────────────────────────────────────────────────

describe('<MasteryTrajectory>', () => {
  it('renders an accessible SVG with a summary label', () => {
    render(<MasteryTrajectory trajectory={sample} windowDays={30} />);
    const svg = screen.getByRole('img', { name: /concept mastery trajectory/i });
    expect(svg).toBeInTheDocument();
  });

  it('renders one legend item per concept with the concept tag', () => {
    render(<MasteryTrajectory trajectory={sample} windowDays={30} />);
    const legend = screen.getByRole('list', { name: /concept legend/i });
    expect(legend).toBeInTheDocument();
    expect(screen.getByText('loop_off_by_one')).toBeInTheDocument();
    expect(screen.getByText('mutable_default_arg')).toBeInTheDocument();
  });

  it('applies the concept color to the legend swatch', () => {
    render(<MasteryTrajectory trajectory={sample} windowDays={30} />);
    const swatches = document.querySelectorAll('[aria-hidden="true"]');
    // The two legend swatches are the first two aria-hidden spans.
    // We assert by data-* — actually, the swatches have inline style.backgroundColor.
    const legendList = screen.getByRole('list', { name: /concept legend/i });
    const swatchNodes = legendList.querySelectorAll('span');
    // Find swatch by inline backgroundColor style
    const violet = Array.from(swatchNodes).find(
      (n) => (n as HTMLElement).style.backgroundColor === 'rgb(124, 58, 237)',
    );
    const cyan = Array.from(swatchNodes).find(
      (n) => (n as HTMLElement).style.backgroundColor === 'rgb(8, 145, 178)',
    );
    expect(violet).toBeDefined();
    expect(cyan).toBeDefined();
  });

  it('shows the current mastery percentage in the legend', () => {
    render(<MasteryTrajectory trajectory={sample} windowDays={30} />);
    // 0.8 → 80%; 0.45 → 45%
    expect(screen.getByText('80%')).toBeInTheDocument();
    expect(screen.getByText('45%')).toBeInTheDocument();
  });

  it('renders the empty state when there is no data', () => {
    const empty: MasteryTrajectoryData = {
      total_events: 0,
      days: 30,
      date_range: { start: null, end: null },
      concepts: [],
    };
    render(<MasteryTrajectory trajectory={empty} windowDays={30} />);
    expect(screen.getByText(/no mastery data yet/i)).toBeInTheDocument();
    // The empty state has NO SVG role=img
    expect(screen.queryByRole('img', { name: /concept mastery trajectory/i })).toBeNull();
  });

  it('draws one line path per concept', () => {
    const { container } = render(
      <MasteryTrajectory trajectory={sample} windowDays={30} />,
    );
    const paths = container.querySelectorAll('path');
    // Two concepts → two path elements (the chart lines)
    expect(paths.length).toBeGreaterThanOrEqual(2);
  });

  it('emits a tooltip title for recent_miss concepts', () => {
    render(<MasteryTrajectory trajectory={sample} windowDays={30} />);
    expect(
      screen.getByText(/mutable_default_arg: last 3 days/i),
    ).toBeInTheDocument();
    // loop_off_by_one has recent_miss=false → no title
    expect(
      screen.queryByText(/loop_off_by_one: last 3 days/i),
    ).toBeNull();
  });

  it('includes a window subtitle describing the data', () => {
    render(<MasteryTrajectory trajectory={sample} windowDays={30} />);
    // 2 concepts, 5 reviews, last 30 days
    expect(
      screen.getByText(/2 concepts.*5 reviews.*last 30 days/i),
    ).toBeInTheDocument();
  });
});
