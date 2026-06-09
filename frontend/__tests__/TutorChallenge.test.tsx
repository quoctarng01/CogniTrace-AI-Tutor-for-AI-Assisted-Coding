import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { TutorChallenge } from '@/components/tracer/TutorChallenge';
import { authFetch } from '@/lib/api';
import type { TraceCheckpoint, TraceStep } from '@/types/trace';

vi.mock('@/lib/api', () => ({
  authFetch: vi.fn(),
}));

describe('TutorChallenge', () => {
  const mockCheckpoint: TraceCheckpoint = {
    step_number: 2,
    line_number: 3,
    checkpoint_type: 'variable_prediction',
    prompt: 'What will be the value of x next?',
    options: ['10', '20', '30'],
    correct_value: '20',
    variable_name: 'x',
    meta: {},
  };

  const mockSteps: TraceStep[] = [];
  const mockOnSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders checkpoint prompt and options', () => {
    render(
      <TutorChallenge
        checkpoint={mockCheckpoint}
        code="x = 10\nif x > 5:\n  x = 20"
        steps={mockSteps}
        onSuccess={mockOnSuccess}
      />
    );

    expect(screen.getByText('◈ AI TUTOR CHALLENGE')).toBeInTheDocument();
    expect(screen.getByText('Predict the Next State')).toBeInTheDocument();
    expect(screen.getByText('What will be the value of x next?')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('20')).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
  });

  it('handles correct answer selection', async () => {
    render(
      <TutorChallenge
        checkpoint={mockCheckpoint}
        code="x = 10"
        steps={mockSteps}
        onSuccess={mockOnSuccess}
      />
    );

    // Select the correct option: '20'
    const correctBtn = screen.getByRole('button', { name: '20' });
    fireEvent.click(correctBtn);

    // Verify correct state is shown
    expect(screen.getByText('Excellent! Your prediction is correct.')).toBeInTheDocument();
    expect(screen.queryByText('Acknowledge & Continue')).not.toBeInTheDocument();

    // Click continue
    const continueBtn = screen.getByRole('button', { name: 'Continue Trace' });
    fireEvent.click(continueBtn);

    expect(mockOnSuccess).toHaveBeenCalledTimes(1);
    expect(authFetch).not.toHaveBeenCalled();
  });

  it('handles incorrect answer and queries LLM diagnose API', async () => {
    const mockDiagnoseResponse = {
      tag: 'state_mutation_confusion',
      explanation: 'You predicted x would be 10, but the block inside the if statement executes since x is greater than 5.',
    };

    // Mock successful API response
    vi.mocked(authFetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockDiagnoseResponse),
    } as unknown as Response);

    render(
      <TutorChallenge
        checkpoint={mockCheckpoint}
        code="x = 10"
        steps={mockSteps}
        onSuccess={mockOnSuccess}
        traceId="test-trace-id"
      />
    );

    // Select the incorrect option: '10'
    const incorrectBtn = screen.getByRole('button', { name: '10' });
    fireEvent.click(incorrectBtn);

    // Check that we display diagnosing state
    expect(screen.getByText(/Diagnosing misconception.../i)).toBeInTheDocument();

    // Verify the API payload
    expect(authFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/llm/diagnose'),
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.any(String),
      })
    );

    const callArgs = vi.mocked(authFetch).mock.calls[0];
    if (!callArgs || !callArgs[1]) {
      throw new Error('Expected authFetch to be called with arguments');
    }
    const bodyObj = JSON.parse(callArgs[1].body as string);
    expect(bodyObj).toEqual({
      code: 'x = 10',
      checkpoint_type: 'variable_prediction',
      variable_name: 'x',
      correct_value: '20',
      user_prediction: '10',
      line_number: 3,
      trace_id: 'test-trace-id',
      steps: mockSteps,
    });

    // Wait for diagnostics to load
    await waitFor(() => {
      expect(screen.getByText('Concept Gap: state mutation confusion')).toBeInTheDocument();
      expect(screen.getByText(mockDiagnoseResponse.explanation)).toBeInTheDocument();
    });

    // Click "Acknowledge & Continue"
    const acknowledgeBtn = screen.getByRole('button', { name: 'Acknowledge & Continue' });
    fireEvent.click(acknowledgeBtn);

    expect(mockOnSuccess).toHaveBeenCalledTimes(1);
  });

  it('handles incorrect answer API error gracefully', async () => {
    // Mock failed API response
    vi.mocked(authFetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    } as unknown as Response);

    render(
      <TutorChallenge
        checkpoint={mockCheckpoint}
        code="x = 10"
        steps={mockSteps}
        onSuccess={mockOnSuccess}
      />
    );

    // Select the incorrect option: '30'
    const incorrectBtn = screen.getByRole('button', { name: '30' });
    fireEvent.click(incorrectBtn);

    // Wait for the error text to show up
    await waitFor(() => {
      expect(screen.getByText(/⚠ Failed to fetch explanation from AI Tutor/i)).toBeInTheDocument();
    });

    // We can still continue by clicking the Acknowledge & Continue button
    const acknowledgeBtn = screen.getByRole('button', { name: 'Acknowledge & Continue' });
    expect(acknowledgeBtn).not.toBeDisabled();
    fireEvent.click(acknowledgeBtn);

    expect(mockOnSuccess).toHaveBeenCalledTimes(1);
  });
});
