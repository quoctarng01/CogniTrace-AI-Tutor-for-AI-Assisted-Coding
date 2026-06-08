// frontend/types/user.ts
import type { TraceStep } from '@/types/trace';

export interface SavedTrace {
  id: string;
  code: string;
  language: string;
  concept_tags: string[];
  is_public: boolean;
  share_token: string;
  created_at: string;
}

export interface ReviewCard {
  id: string;
  trace_id: string;
  concept_tag: string;
  next_review_date: string; // ISO "YYYY-MM-DD" — string, NOT Date
  interval_days: number;
  easiness_factor: number;
  repetitions: number;
  due: boolean;
  trace?: SavedTrace & { steps?: TraceStep[] };
  code_repair_challenge?: string | null;
}

export interface DashboardData {
  traces: SavedTrace[];
  due_cards: ReviewCard[];
  streak: number;
  total_traces: number;
}

export interface DueReviewsData {
  cards: ReviewCard[];
  streak: number;
  total_due: number;
}

export interface SaveTraceResponse {
  id: string;
  share_token: string;
  created_at: string;
}

export interface SubmitReviewResponse {
  next_review_date: string;
  new_interval_days: number;
}

/** Single review card with full trace + steps — returned by GET /api/review/{card_id} */
export interface ReviewCardDetail {
  id: string;
  trace_id: string;
  concept_tag: string;
  next_review_date: string;
  interval_days: number;
  easiness_factor: number;
  repetitions: number;
  due: boolean;
  trace: SavedTrace & { steps: TraceStep[] };
  code_repair_challenge?: string | null;
}

/** Shared trace with embedded steps — returned by GET /api/traces/shared/{share_token} */
export interface SharedTraceData {
  id: string;
  code: string;
  language: string;
  concept_tags: string[];
  is_public: boolean;
  share_token: string;
  created_at: string;
  steps: TraceStep[];
}
