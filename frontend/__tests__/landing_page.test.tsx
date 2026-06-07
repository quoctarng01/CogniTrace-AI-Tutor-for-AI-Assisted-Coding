import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Home from '@/app/page';

describe('Landing Page', () => {
  it('renders hero section with title', () => {
    render(<Home />);

    expect(screen.getByText(/Pasted AI-generated code/i)).toBeInTheDocument();
    expect(screen.getByText(/No idea why it is breaking/i)).toBeInTheDocument();
  });

  it('renders feature cards', () => {
    render(<Home />);

    expect(screen.getByRole('heading', { name: /Step-by-Step Execution/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Branch Detection/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /AI Explanations/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Spaced Repetition/i })).toBeInTheDocument();
  });

  it('renders CTA button', () => {
    render(<Home />);

    expect(screen.getByText(/Start Tracing →/i)).toBeInTheDocument();
  });

  it('renders code examples section', () => {
    render(<Home />);

    expect(screen.getByText(/Try Common Patterns/i)).toBeInTheDocument();
  });
});
