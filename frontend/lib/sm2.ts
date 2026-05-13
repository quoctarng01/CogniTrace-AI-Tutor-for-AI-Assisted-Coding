/**
 * SM-2 Spaced Repetition Algorithm.
 * 
 * Implementation of the SuperMemo 2 algorithm for scheduling review sessions.
 * 
 * Quality ratings:
 *   again (0) → quality 1 — complete blackout, reset to 1 day
 *   hard (1)  → quality 2 — incorrect but remembered easily
 *   good (2)   → quality 3 — correct with some difficulty
 *   easy (3)   → quality 5 — perfect recall
 * 
 * Easiness Factor (EF):
 *   Minimum: 1.3
 *   Default: 2.5
 *   Formula: EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
 */

export type Rating = "again" | "hard" | "good" | "easy";

export interface SM2Params {
  quality: number;        // 0-5
  easinessFactor: number; // minimum 1.3
  intervalDays: number;   // current interval
  repetitions: number;    // consecutive correct answers
}

export interface SM2Result {
  newEasinessFactor: number;
  newIntervalDays: number;
  newRepetitions: number;
  nextReviewDate: Date;
}

const MIN_EF = 1.3;

const RATING_MAP: Record<Rating, number> = {
  again: 1,
  hard: 2,
  good: 3,
  easy: 5,
};

export function sm2(rating: Rating, params: Omit<SM2Params, "quality">): SM2Result {
  const { easinessFactor: ef, intervalDays: interval, repetitions: reps } = params;
  const q = RATING_MAP[rating];

  // Update easiness factor
  // EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
  let newEF = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02));
  newEF = Math.max(MIN_EF, newEF);

  // Calculate new interval and repetitions
  let newInterval: number;
  let newReps: number;

  if (q < 3) {
    // Failed — reset
    newInterval = 1;
    newReps = 0;
  } else {
    if (reps === 0) {
      newInterval = 1;
    } else if (reps === 1) {
      newInterval = 6;
    } else {
      newInterval = Math.round(interval * newEF);
    }
    newReps = reps + 1;
  }

  // Calculate next review date
  const nextReview = new Date();
  if (q >= 3) {
    nextReview.setDate(nextReview.getDate() + newInterval);
  }

  return {
    newEasinessFactor: Math.round(newEF * 100) / 100,
    newIntervalDays: newInterval,
    newRepetitions: newReps,
    nextReviewDate: nextReview,
  };
}

export function reviewToSM2Params(card: {
  easiness_factor: number;
  interval_days: number;
  repetitions: number;
}): SM2Params {
  return {
    quality: 0,  // Will be set by caller
    easinessFactor: card.easiness_factor,
    intervalDays: card.interval_days,
    repetitions: card.repetitions,
  };
}

export function calculateStreak(reviewHistory: Array<{ date: string }>): number {
  if (reviewHistory.length === 0) return 0;

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // Get unique review dates
  const reviewDates = new Set(
    reviewHistory.map((r) => {
      const d = new Date(r.date);
      d.setHours(0, 0, 0, 0);
      return d.getTime();
    })
  );

  let streak = 0;
  let checkDate = new Date(today);

  while (reviewDates.has(checkDate.getTime()) || 
         (streak === 0 && reviewDates.has(new Date(checkDate.getTime() - 86400000).getTime()))) {
    if (reviewDates.has(checkDate.getTime())) {
      streak++;
    }
    checkDate.setDate(checkDate.getDate() - 1);
  }

  return streak;
}

export function formatNextReview(date: Date): string {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const target = new Date(date);
  target.setHours(0, 0, 0, 0);

  const diffDays = Math.round((target.getTime() - today.getTime()) / 86400000);

  if (diffDays <= 0) return "Due today";
  if (diffDays === 1) return "Due tomorrow";
  if (diffDays < 7) return `Due in ${diffDays} days`;
  if (diffDays < 30) return `Due in ${Math.round(diffDays / 7)} weeks`;
  return `Due in ${Math.round(diffDays / 30)} months`;
}
