'use client';

import { useCallback, useRef, useEffect } from 'react';
import type { PlaybackSpeed, PlaybackState } from '@/hooks/useTrace';
import type { TraceStep } from '@/types/trace';
import styles from './AnimationControls.module.css';

interface AnimationControlsProps {
  steps: TraceStep[];
  currentStep: number;
  onStepChange: (step: number) => void;
  totalSteps: number;
  durationMs: number;
  // useTrace state passed from parent (FIX-MD-07)
  playbackState: PlaybackState;
  speed: PlaybackSpeed;
  play: () => void;
  pause: () => void;
  togglePlayPause: () => void;
  stepForward: () => void;
  stepBackward: () => void;
  jumpToStep: (step: number) => void;
  setSpeed: (speed: PlaybackSpeed) => void;
  reset: () => void;
}

export function AnimationControls({
  steps,
  currentStep,
  onStepChange,
  totalSteps,
  durationMs,
  playbackState,
  speed,
  play,
  pause,
  togglePlayPause,
  stepForward,
  stepBackward,
  jumpToStep,
  setSpeed,
  reset,
}: AnimationControlsProps) {
  // FIX-MD-07: useTrace is called in parent (page.tsx), not here
  // This prevents the double-hook problem that caused inconsistent state

  const hookStep = currentStep; // Use prop instead of internal hook state
  const SPEEDS: PlaybackSpeed[] = [0.5, 1, 2, 5];

  const progressPercent = totalSteps > 0 ? (hookStep / (totalSteps - 1)) * 100 : 0;

  // Handle jump via slider or buttons
  const handleJumpTo = useCallback(
    (step: number) => {
      jumpToStep(step);
      onStepChange(step);
    },
    [jumpToStep, onStepChange]
  );

  return (
    <div className={styles.controls}>
      {/* Progress bar */}
      <div className={styles.progressContainer}>
        <span className={styles.stepLabel}>
          Step {hookStep + 1} / {totalSteps}
        </span>
        <div className={styles.progressTrack}>
          <div className={styles.progressFill} style={{ width: `${progressPercent}%` }} />
        </div>
        <span className={styles.durationLabel}>
          {durationMs > 0 ? `${(durationMs / 1000).toFixed(1)}s` : ''}
        </span>
      </div>

      {/* Control buttons */}
      <div className={styles.buttonRow}>
        {/* Reset */}
        <button
          className={styles.iconBtn}
          onClick={reset}
          title="Reset (Home)"
          aria-label="Reset to beginning"
        >
          ⏮
        </button>

        {/* Step back */}
        <button
          className={styles.iconBtn}
          onClick={() => {
            stepBackward();
            onStepChange(Math.max(0, hookStep - 1));
          }}
          disabled={hookStep === 0}
          title="Step backward (←)"
          aria-label="Step backward"
        >
          ◀
        </button>

        {/* Play / Pause */}
        <button
          className={`${styles.playBtn} ${playbackState === 'playing' ? styles.playing : ''}`}
          onClick={togglePlayPause}
          title={`${playbackState === 'playing' ? 'Pause' : 'Play'} (Space)`}
          aria-label={playbackState === 'playing' ? 'Pause' : 'Play'}
        >
          {playbackState === 'playing' ? '⏸' : '▶'}
        </button>

        {/* Step forward */}
        <button
          className={styles.iconBtn}
          onClick={() => {
            stepForward();
            onStepChange(Math.min(totalSteps - 1, hookStep + 1));
          }}
          disabled={hookStep >= totalSteps - 1}
          title="Step forward (→)"
          aria-label="Step forward"
        >
          ▶
        </button>

        {/* Jump to end */}
        <button
          className={styles.iconBtn}
          onClick={() => handleJumpTo(totalSteps - 1)}
          disabled={hookStep >= totalSteps - 1}
          title="Jump to end (End)"
          aria-label="Jump to end"
        >
          ⏭
        </button>

        {/* Speed selector */}
        <div className={styles.speedSelector}>
          {SPEEDS.map(s => (
            <button
              key={s}
              className={`${styles.speedBtn} ${speed === s ? styles.activeSpeed : ''}`}
              onClick={() => setSpeed(s)}
              aria-label={`Set speed to ${s}x`}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>

      {/* State indicator */}
      {playbackState === 'ended' && (
        <div className={styles.stateIndicator}>Trace complete — press ← to review</div>
      )}
    </div>
  );
}
