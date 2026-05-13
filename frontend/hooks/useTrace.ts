/**
 * useTrace — manages trace playback with rAF-based animation loop.
 * 
 * CRITICAL FIX (vs original setInterval approach):
 * - Uses requestAnimationFrame with elapsed time tracking
 * - Pauses automatically when tab is hidden (visibilitychange)
 * - Synchronized with rendering — no accumulated drift
 * - Step-accurate timing regardless of tab focus state
 * 
 * Original problem with setInterval:
 *   - setInterval fires even when tab is backgrounded
 *   - Steps accumulate and then jump when tab becomes visible
 *   - Not synchronized with rendering, causing visual stutter
 * 
 * Speed → interval mapping:
 *   1× → 750ms per step
 *   2× → 375ms per step
 *   5× → 150ms per step
 *   0.5× → 1500ms per step
 */

import { useState, useEffect, useCallback, useRef } from "react";
import type { TraceStep } from "@/types/trace";

export type PlaybackSpeed = 0.5 | 1 | 2 | 5;
export type PlaybackState = "idle" | "playing" | "paused" | "ended";

const SPEED_MS: Record<PlaybackSpeed, number> = {
  0.5: 1500,
  1: 750,
  2: 375,
  5: 150,
};

export interface UseTraceOptions {
  steps: TraceStep[];
  autoPlay?: boolean;
  initialStep?: number;
}

export interface UseTraceReturn {
  // State
  currentStep: number;
  playbackState: PlaybackState;
  speed: PlaybackSpeed;
  currentStepData: TraceStep | null;
  
  // Controls
  play: () => void;
  pause: () => void;
  togglePlayPause: () => void;
  stepForward: () => void;
  stepBackward: () => void;
  jumpToStep: (step: number) => void;
  setSpeed: (speed: PlaybackSpeed) => void;
  reset: () => void;
}

export function useTrace({
  steps,
  autoPlay = false,
  initialStep = 0,
}: UseTraceOptions): UseTraceReturn {
  const [currentStep, setCurrentStep] = useState(initialStep);
  const [playbackState, setPlaybackState] = useState<PlaybackState>(
    autoPlay && steps.length > 0 ? "playing" : "idle"
  );
  const [speed, setSpeedState] = useState<PlaybackSpeed>(1);

  // Refs for the animation loop
  const rafRef = useRef<number | null>(null);
  const lastStepTimeRef = useRef<number>(0);
  const accumulatedTimeRef = useRef<number>(0);
  const isPlayingRef = useRef<boolean>(false);
  const pausedStepRef = useRef<number>(initialStep);

  const totalSteps = steps.length;
  const intervalMs = SPEED_MS[speed];

  // Current step data
  const currentStepData = steps[currentStep] ?? null;

  // ── Animation Loop ──────────────────────────────────────────────

  const animationLoop = useCallback(
    (timestamp: number) => {
      if (!isPlayingRef.current || steps.length === 0) {
        return;
      }

      // Initialize timing on first frame
      if (lastStepTimeRef.current === 0) {
        lastStepTimeRef.current = timestamp;
        rafRef.current = requestAnimationFrame(animationLoop);
        return;
      }

      const elapsed = timestamp - lastStepTimeRef.current;
      lastStepTimeRef.current = timestamp;

      // Only accumulate if it's a reasonable frame time (avoid huge values from tab switching)
      if (elapsed < 1000) {
        accumulatedTimeRef.current += elapsed;
      }

      const currentStepRef = pausedStepRef.current;

      if (accumulatedTimeRef.current >= intervalMs) {
        accumulatedTimeRef.current -= intervalMs;  // Carry over excess time
        lastStepTimeRef.current = timestamp;

        if (currentStepRef < totalSteps - 1) {
          pausedStepRef.current = currentStepRef + 1;
          setCurrentStep(currentStepRef + 1);
        } else {
          // End of trace
          isPlayingRef.current = false;
          setPlaybackState("ended");
          return;  // Stop the loop
        }
      }

      rafRef.current = requestAnimationFrame(animationLoop);
    },
    [steps, intervalMs, totalSteps]
  );

  // Start animation loop
  const play = useCallback(() => {
    if (totalSteps === 0) return;
    if (pausedStepRef.current >= totalSteps - 1) {
      // Reset to beginning if at end
      pausedStepRef.current = 0;
      setCurrentStep(0);
    }

    isPlayingRef.current = true;
    lastStepTimeRef.current = 0;
    accumulatedTimeRef.current = 0;
    setPlaybackState("playing");

    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
    }
    rafRef.current = requestAnimationFrame(animationLoop);
  }, [totalSteps, animationLoop]);

  // Pause animation loop
  const pause = useCallback(() => {
    isPlayingRef.current = false;
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    pausedStepRef.current = currentStep;
    setPlaybackState("paused");
  }, [currentStep]);

  // Toggle play/pause
  const togglePlayPause = useCallback(() => {
    if (isPlayingRef.current) {
      pause();
    } else {
      play();
    }
  }, [play, pause]);

  // Step forward one step
  const stepForward = useCallback(() => {
    pause();  // Always pause before manual step
    if (pausedStepRef.current < totalSteps - 1) {
      pausedStepRef.current += 1;
      setCurrentStep(pausedStepRef.current);
      setPlaybackState("paused");
    } else {
      setPlaybackState("ended");
    }
  }, [pause, totalSteps]);

  // Step backward one step
  const stepBackward = useCallback(() => {
    pause();  // Always pause before manual step
    if (pausedStepRef.current > 0) {
      pausedStepRef.current -= 1;
      setCurrentStep(pausedStepRef.current);
      setPlaybackState("paused");
    } else {
      setPlaybackState("paused");
    }
  }, [pause]);

  // Jump to specific step
  const jumpToStep = useCallback(
    (step: number) => {
      const clampedStep = Math.max(0, Math.min(step, totalSteps - 1));
      pause();
      pausedStepRef.current = clampedStep;
      setCurrentStep(clampedStep);
      setPlaybackState(clampedStep === totalSteps - 1 ? "ended" : "paused");
    },
    [pause, totalSteps]
  );

  // Set playback speed
  const setSpeed = useCallback((newSpeed: PlaybackSpeed) => {
    setSpeedState(newSpeed);
    // Reset accumulated time so next step respects new speed
    accumulatedTimeRef.current = 0;
    lastStepTimeRef.current = 0;
  }, []);

  // Reset to beginning
  const reset = useCallback(() => {
    pause();
    pausedStepRef.current = 0;
    setCurrentStep(0);
    setPlaybackState("idle");
    accumulatedTimeRef.current = 0;
  }, [pause]);

  // ── Tab visibility handling ─────────────────────────────────────

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Tab is hidden — pause to avoid accumulated steps
        if (isPlayingRef.current) {
          pause();
        }
      }
      // When tab becomes visible again, user can manually resume
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [pause]);

  // ── Keyboard shortcuts ──────────────────────────────────────────

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only handle if not in a text input
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
        return;
      }

      switch (e.key) {
        case " ":
          e.preventDefault();
          togglePlayPause();
          break;
        case "ArrowRight":
          e.preventDefault();
          if (isPlayingRef.current) pause();
          stepForward();
          break;
        case "ArrowLeft":
          e.preventDefault();
          if (isPlayingRef.current) pause();
          stepBackward();
          break;
        case "Home":
          e.preventDefault();
          reset();
          break;
        case "End":
          e.preventDefault();
          jumpToStep(totalSteps - 1);
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [togglePlayPause, stepForward, stepBackward, reset, jumpToStep, pause, totalSteps]);

  // ── Cleanup on unmount ──────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  // ── Sync step ref when currentStep changes externally ──────────

  useEffect(() => {
    pausedStepRef.current = currentStep;
  }, [currentStep]);

  return {
    currentStep,
    playbackState,
    speed,
    currentStepData,
    play,
    pause,
    togglePlayPause,
    stepForward,
    stepBackward,
    jumpToStep,
    setSpeed,
    reset,
  };
}
