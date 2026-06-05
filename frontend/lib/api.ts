/**
 * API client — typed fetch wrappers for all CodeScope endpoints.
 */
import type { TraceStep } from '@/types/trace';
import type { AnalyzeResponse } from '@/types/annotation';
import type {
  DashboardData,
  DueReviewsData,
  SaveTraceResponse,
  SubmitReviewResponse,
  SavedTrace,
  ReviewCardDetail,
  SharedTraceData,
} from '@/types/user';
import { getAuthToken } from '@/lib/supabase';

// ── Constants ─────────────────────────────────────────────────────

/** Maximum code length allowed per trace (in characters). */
const MAX_CODE_LENGTH = 5000;

// ── Types ─────────────────────────────────────────────────────────

export interface TraceRunRequest {
  code: string;
}

export interface TraceRunResponse {
  trace_id: string;
  steps: TraceStep[];
  total_steps: number;
  duration_ms: number;
  error?: string;
  error_message?: string;
}

export interface TraceSaveRequest {
  code: string;
  concept_tags: string[];
  is_public: boolean;
}

export interface TraceSaveResponse {
  id: string;
  share_token: string;
  created_at: string;
}

export interface ExplanationParams {
  code: string;
  line_number: number;
  line_content: string;
  locals: Record<string, { type: string; value: string }>;
}

export interface ReviewCard {
  id: string;
  trace_id: string;
  concept_tag: string;
  next_review_date: string;
  interval_days: number;
  easiness_factor: number;
  repetitions: number;
  due: boolean;
}

export interface DueReviewsResponse {
  cards: ReviewCard[];
  streak: number;
  total_due: number;
}

export interface Profile {
  id: string;
  experience_level: 'student' | 'junior' | 'mid';
  ai_tools_usage: 'none' | 'light' | 'moderate' | 'heavy';
  ollama_endpoint: string;
  plan: 'free' | 'pro';
}

// ── Error Handling ────────────────────────────────────────────────

/**
 * Check response status and throw appropriate errors.
 * Consolidates repeated error handling patterns across the API.
 */
function throwOnStatus(res: Response, path: string): void {
  if (res.status === 401) throw new Error('AUTH_REQUIRED');
  if (res.status === 404) throw new Error(`${path}_NOT_FOUND`);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
}

// ── API Client ───────────────────────────────────────────────────

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000') + '/api';

/**
 * Get the base API URL (used by standalone functions outside the class).
 * Centralizes the env var + fallback pattern.
 */
function getApiBase(): string {
  return API_BASE;
}

class CodeScopeAPI {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl ?? API_BASE;
  }

  setToken(token: string | null) {
    this.token = token;
  }

  private async fetch<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const res = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      let errorBody: Record<string, unknown> = {};
      try {
        errorBody = await res.json();
      } catch (_err) {
        errorBody = { message: res.statusText };
      }

      const error = new Error(
        (errorBody.message as string) || (errorBody.detail as string) || `HTTP ${res.status}`
      ) as Error & { status: number; body: Record<string, unknown> };
      error.status = res.status;
      error.body = errorBody;
      throw error;
    }

    if (res.status === 204) {
      return {} as T;
    }

    return res.json();
  }

  // ── Traces ────────────────────────────────────────────────────

  async runTrace(code: string): Promise<TraceRunResponse> {
    return this.fetch<TraceRunResponse>('/traces/run', {
      method: 'POST',
      body: JSON.stringify({ code }),
    });
  }

  async analyzeCode(code: string): Promise<AnalyzeResponse> {
    return this.fetch<AnalyzeResponse>('/analyze', {
      method: 'POST',
      body: JSON.stringify({ code }),
    });
  }

  async saveTrace(req: TraceSaveRequest): Promise<TraceSaveResponse> {
    return this.fetch<TraceSaveResponse>('/traces', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  }

  async getTraces(): Promise<{ traces: unknown[] }> {
    return this.fetch<{ traces: unknown[] }>('/traces');
  }

  // ── Reviews ──────────────────────────────────────────────────

  async getDueReviews(): Promise<DueReviewsResponse> {
    return this.fetch<DueReviewsResponse>('/review/due');
  }

  async submitReview(
    cardId: string,
    rating: 'again' | 'hard' | 'good' | 'easy'
  ): Promise<{
    card_id: string;
    new_interval_days: number;
    new_ef: number;
    new_repetitions: number;
    next_review_date: string;
  }> {
    return this.fetch(`/review/${cardId}`, {
      method: 'POST',
      body: JSON.stringify({ rating }),
    });
  }

  // ── Profiles ──────────────────────────────────────────────────

  async getProfile(): Promise<Profile> {
    return this.fetch<Profile>('/profiles/me');
  }

  async updateProfile(
    updates: Partial<Pick<Profile, 'experience_level' | 'ai_tools_usage' | 'ollama_endpoint'>>
  ): Promise<Profile> {
    return this.fetch<Profile>('/profiles/me', {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }
}

// Singleton
export const api = new CodeScopeAPI();

// ── Standalone auth-fetch helper ─────────────────────────────────

const logger = {
  debug: (...args: unknown[]) => {
    if (process.env.NODE_ENV === 'development') console.log(...args);
  },
};

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = await getAuthToken();
  logger.debug('[authFetch] token:', token ? `${token.substring(0, 30)}...` : 'NULL');
  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
    logger.debug('[authFetch] Sending Authorization header');
  } else {
    logger.debug('[authFetch] NO Authorization header - token is null');
  }
  return fetch(url, { ...options, headers });
}

// ── Dashboard / Traces ─────────────────────────────────────────

export async function fetchDashboard(): Promise<DashboardData> {
  const res = await authFetch(`${getApiBase()}/traces`);
  throwOnStatus(res, 'dashboard');
  return res.json();
}

export async function saveTrace(params: {
  code: string;
  language?: string;
  steps: TraceStep[];
  concept_tags?: string[];
}): Promise<SaveTraceResponse> {
  if (params.code.length > MAX_CODE_LENGTH) {
    throw new Error(`Code exceeds ${MAX_CODE_LENGTH} character limit`);
  }
  const res = await authFetch(`${getApiBase()}/traces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      code: params.code,
      language: params.language ?? 'python',
      steps: params.steps,
      concept_tags: params.concept_tags ?? [],
    }),
  });
  if (res.status === 401) throw new Error('AUTH_REQUIRED');
  if (res.status === 402) throw new Error('UPGRADE_REQUIRED');
  throwOnStatus(res, 'trace');
  return res.json();
}

// ── Review ──────────────────────────────────────────────────────

/**
 * Fetch a single review card with its full trace + steps.
 * Called by /review/[card_id] — one API call, full data returned.
 */
export async function fetchReviewCard(cardId: string): Promise<ReviewCardDetail> {
  const res = await authFetch(`${getApiBase()}/review/${cardId}`);
  throwOnStatus(res, 'review card');
  return res.json();
}

export async function fetchDueReviews(): Promise<DueReviewsData> {
  const res = await authFetch(`${getApiBase()}/review/due`);
  throwOnStatus(res, 'reviews');
  return res.json();
}

export async function submitReviewRating(
  cardId: string,
  rating: 'again' | 'hard' | 'good' | 'easy'
): Promise<SubmitReviewResponse> {
  const res = await authFetch(`${getApiBase()}/review/${cardId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rating }),
  });
  throwOnStatus(res, 'review');
  return res.json();
}

// ── Shared trace ────────────────────────────────────────────────

export async function fetchSharedTrace(shareToken: string): Promise<SharedTraceData> {
  const res = await fetch(`${getApiBase()}/traces/shared/${shareToken}`);
  throwOnStatus(res, 'trace');
  return res.json();
}

export async function shareTrace(
  traceId: string,
  options?: {
    expiration_days?: number;
    password?: string;
  }
): Promise<{ share_token: string; share_url: string; expires_at: string | null; has_password: boolean }> {
  const body: Record<string, unknown> = {};
  if (options?.expiration_days !== undefined) {
    body.expiration_days = options.expiration_days;
  }
  if (options?.password) {
    body.password = options.password;
  }
  const res = await authFetch(`${getApiBase()}/traces/${traceId}/share`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.status === 401) throw new Error('AUTH_REQUIRED');
  if (!res.ok) throw new Error(`Failed to generate share link: ${res.status}`);
  return res.json();
}

// ── Re-export runTrace for convenience ──────────────────────────

export async function runTrace(
  code: string,
  options?: {
    initialNamespace?: Record<string, string>;
  }
): Promise<{ trace_id: string; steps: TraceStep[]; total_steps: number; duration_ms: number; error?: string; error_message?: string }> {
  const body: Record<string, unknown> = { code };
  if (options?.initialNamespace) {
    body.initial_namespace = options.initialNamespace;
  }
  const res = await fetch(`${getApiBase()}/traces/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail?.error ?? err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Example Library ─────────────────────────────────────────────

export interface ExampleAnnotation {
  line: number;
  text: string;
  type: string;
}

export interface Example {
  id: string;
  category: string;
  title: string;
  code: string;
  why_ai_generates_this: string | null;
  annotations: ExampleAnnotation[];
  explanation: string;
  common_mistakes: string[];
  review_interval: string;
}

export interface ExampleListResponse {
  examples: Example[];
  total: number;
  limit: number;
  offset: number;
}

export interface SaveToQueueResponse {
  card_id: string;
  message: string;
  existing: boolean;
}

/**
 * Fetch all examples from /api/examples.
 * Auth: NOT required (public endpoint).
 * @param category  Optional category filter, e.g. "comprehensions"
 * @param limit     Results per page (default 20, max 50)
 * @param offset    Skip N results (default 0)
 */
export async function fetchExamples(
  category?: string,
  limit = 20,
  offset = 0
): Promise<ExampleListResponse> {
  const params = new URLSearchParams();
  if (category) params.set('category', category);
  params.set('limit', String(limit));
  params.set('offset', String(offset));

  const url = `${getApiBase()}/examples?${params}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch examples: ${res.status}`);
  return res.json();
}

/**
 * Fetch a single example by ID from /api/examples/{id}.
 * Auth: NOT required.
 */
export async function fetchExample(id: string): Promise<Example> {
  const url = `${getApiBase()}/examples/${encodeURIComponent(id)}`;
  const res = await fetch(url);
  if (res.status === 404) throw new Error('EXAMPLE_NOT_FOUND');
  if (!res.ok) throw new Error(`Failed to fetch example: ${res.status}`);
  return res.json();
}

/**
 * Save an example to the authenticated user's review queue.
 * Auth: Required (Pro plan only).
 * Creates a review_card (with a pseudo-trace) so the example appears in the review schedule.
 */
export async function saveExampleToReview(exampleId: string): Promise<SaveToQueueResponse> {
  const token = await _getAuthToken();
  if (!token) throw new Error('AUTH_REQUIRED');

  const res = await fetch(`${getApiBase()}/examples/${encodeURIComponent(exampleId)}/save`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });

  if (res.status === 401) throw new Error('AUTH_REQUIRED');
  if (res.status === 403) {
    const body = await res.json().catch(() => ({}));
    throw Object.assign(new Error('UPGRADE_REQUIRED'), { detail: body.detail });
  }
  if (res.status === 404) throw new Error('EXAMPLE_NOT_FOUND');
  if (!res.ok) throw new Error(`Failed to save example: ${res.status}`);
  return res.json();
}

/** Helper: get the Supabase auth token. */
async function _getAuthToken(): Promise<string | null> {
  try {
    const { getSupabase } = await import('@/lib/supabase');
    const { data } = await getSupabase().auth.getSession();
    return data.session?.access_token ?? null;
  } catch {
    return null;
  }
}
