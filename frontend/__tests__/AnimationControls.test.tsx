import { render, screen, fireEvent } from '@testing-library/react';
import { AnimationControls } from '@/components/tracer/AnimationControls';

describe('AnimationControls', () => {
  it('shows play button when paused', () => {
    render(<AnimationControls isPlaying={false} onTogglePlay={jest.fn()} />);
    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
  });

  it('shows pause button when playing', () => {
    render(<AnimationControls isPlaying={true} onTogglePlay={jest.fn()} />);
    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
  });

  it('step back is disabled at step 0', () => {
    render(
      <AnimationControls
        isPlaying={false}
        onTogglePlay={jest.fn()}
        currentStep={0}
        totalSteps={10}
        onStepBack={jest.fn()}
        onStepForward={jest.fn()}
      />
    );
    expect(screen.getByRole('button', { name: /back/i })).toBeDisabled();
  });

  it('step forward is disabled at last step', () => {
    render(
      <AnimationControls
        isPlaying={false}
        onTogglePlay={jest.fn()}
        currentStep={9}
        totalSteps={10}
        onStepBack={jest.fn()}
        onStepForward={jest.fn()}
      />
    );
    expect(screen.getByRole('button', { name: /forward/i })).toBeDisabled();
  });

  it('Space key toggles play when not in text input', () => {
    const onTogglePlay = jest.fn();
    render(<AnimationControls isPlaying={false} onTogglePlay={onTogglePlay} />);
    fireEvent.keyDown(document, { key: ' ' });
    expect(onTogglePlay).toHaveBeenCalledTimes(1);
  });
});
