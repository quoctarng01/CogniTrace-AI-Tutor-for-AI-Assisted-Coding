import { render, screen } from '@testing-library/react';
import { AnimationControls } from '@/components/tracer/AnimationControls';

const defaultProps = {
  steps: [],
  currentStep: 0,
  onStepChange: vi.fn(),
  totalSteps: 10,
  durationMs: 1000,
  playbackState: 'paused' as const,
  speed: 1 as const,
  play: vi.fn(),
  pause: vi.fn(),
  togglePlayPause: vi.fn(),
  stepForward: vi.fn(),
  stepBackward: vi.fn(),
  jumpToStep: vi.fn(),
  setSpeed: vi.fn(),
  reset: vi.fn(),
};

describe('AnimationControls', () => {
  it('shows play button when paused', () => {
    render(<AnimationControls {...defaultProps} playbackState="paused" />);
    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
  });

  it('shows pause button when playing', () => {
    render(<AnimationControls {...defaultProps} playbackState="playing" />);
    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
  });

  it('step back is disabled at step 0', () => {
    render(<AnimationControls {...defaultProps} currentStep={0} />);
    expect(screen.getByRole('button', { name: /step backward/i })).toBeDisabled();
  });

  it('step forward is disabled at last step', () => {
    render(<AnimationControls {...defaultProps} currentStep={9} totalSteps={10} />);
    expect(screen.getByRole('button', { name: /step forward/i })).toBeDisabled();
  });
});
