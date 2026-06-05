import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Home from '@/app/page';

describe('Landing Page', () => {
  it('renders hero section with title', () => {
    render(<Home />);

    expect(screen.getByText(/Understand Python Code/)).toBeInTheDocument();
    expect(screen.getByText(/One Step at a Time/)).toBeInTheDocument();
  });

  it('renders feature cards', () => {
    render(<Home />);

    expect(screen.getByText(/Step-by-Step Execution/)).toBeInTheDocument();
    expect(screen.getByText(/Branch Detection/)).toBeInTheDocument();
    expect(screen.getByText(/AI Explanations/)).toBeInTheDocument();
    expect(screen.getByText(/Spaced Repetition/)).toBeInTheDocument();
  });

  it('renders CTA button', () => {
    render(<Home />);

    expect(screen.getByText(/Start Tracing/)).toBeInTheDocument();
  });

  it('renders code examples section', () => {
    render(<Home />);

    expect(screen.getByText(/Try Common Patterns/)).toBeInTheDocument();
  });
});
