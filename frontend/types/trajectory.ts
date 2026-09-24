/**
 * Type definitions for the per-concept mastery trajectory visualization
 * (THESIS-05 §2). Returned by GET /api/review/trajectory.
 */
import type { Rating } from '@/lib/sm2';

export interface TrajectoryPoint {
  /** ISO date (YYYY-MM-DD) of the review. */
  date: string;
  /** 0..1 mastery score, monotone in SM-2 repetitions. */
  mastery: number;
  /** The rating the student pressed for this review. */
  rating: Rating;
  /** SM-2 repetitions *after* this rating was applied. */
  repetitions: number;
  /** SM-2 interval (days) *after* this rating was applied. */
  interval_days: number;
}

export interface TrajectoryConcept {
  concept_tag: string;
  /** CSS hex colour, drawn from a deterministic 8-slot palette. */
  color: string;
  total_reviews: number;
  /** Mastery score at the most recent point. */
  current_mastery: number;
  /** True if any hard/again rating occurred in the last 3 calendar days. */
  recent_miss: boolean;
  points: TrajectoryPoint[];
}

export interface MasteryTrajectory {
  concepts: TrajectoryConcept[];
  date_range: { start: string | null; end: string | null };
  total_events: number;
  /** Window size in days, as requested by the client. */
  days: number;
}
