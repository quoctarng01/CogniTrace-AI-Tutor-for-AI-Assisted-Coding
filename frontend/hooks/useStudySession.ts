/**
 * useStudySession — assigns and persists an opaque pilot-session UUID.
 *
 * On first mount, the hook reads `cognitrace_study_session` from localStorage.
 * If absent, it generates a fresh v4 UUID and stores it. The hook returns the
 * UUID so callers can:
 *   - send it as `X-Study-Session` on every fetch
 *   - attach it to a study_sessions row server-side when the participant
 *     provides their anonymized study_id ('P001', etc.)
 *
 * The session UUID survives page reloads but is cleared on explicit logout.
 * For production traffic (no study_id enrolled), it is still safe to send
 * the header; the backend will write rows tagged with the UUID but with
 * `study_id` left NULL. See `docs/THESIS-04-REGISTRATION-FORM-DRAFT.md`
 * for the W1 pilot plan.
 */
'use client';

import { useEffect, useState } from 'react';

const STORAGE_KEY = 'cognitrace_study_session';
const STUDY_ID_STORAGE_KEY = 'cognitrace_study_id';
const CONDITION_STORAGE_KEY = 'cognitrace_study_condition';
const TASK_ID_STORAGE_KEY = 'cognitrace_study_task_id';

function generateUuidV4(): string {
  // Lightweight v4 UUID — good enough for telemetry. Does not require crypto
  // polyfills; safe in browsers without `crypto.randomUUID` support.
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  // RFC 4122 fallback (Math.random — acceptable for non-cryptographic telemetry).
  const r = (n: number) =>
    Math.floor(Math.random() * Math.pow(16, n)).toString(16).padStart(n, '0');
  return [
    r(8),
    r(4),
    '4' + r(3),     // version 4
    ((8 + Math.floor(Math.random() * 4)).toString(16)) + r(3), // variant 10xx
    r(12),
  ].join('-');
}

export interface StudySessionState {
  /** Opaque v4 UUID. Sourced from localStorage; regenerated only when cleared. */
  sessionId: string;
  /** Anonymized participant code (`P001`, etc.). `null` if not yet enrolled. */
  studyId: string | null;
  /** Within-subjects condition for this session: 'A' | 'B' | 'C' | "C'" | null. */
  condition: string | null;
  /** Identifier of the debugging task the participant is currently attempting. */
  taskId: string | null;
}

export interface UseStudySessionReturn extends StudySessionState {
  /** Update the anonymized participant code (called once on enrollment). */
  enroll: (studyId: string) => void;
  /** Update the within-subjects condition (called by pilot state machine). */
  setCondition: (condition: string) => void;
  /** Update the current task id (called when the participant advances). */
  setTaskId: (taskId: string) => void;
  /** Wipe the session from localStorage (e.g. on explicit logout). */
  clear: () => void;
}

function readFromStorage<T extends string>(key: string): T | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(key) as T | null;
  } catch {
    return null;
  }
}

function writeToStorage(key: string, value: string | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // localStorage may be unavailable (private mode, quota, etc.) — fail silent.
  }
}

export function useStudySession(): UseStudySessionReturn {
  const [sessionId, setSessionId] = useState<string>('');
  const [studyId, setStudyIdState] = useState<string | null>(null);
  const [condition, setConditionState] = useState<string | null>(null);
  const [taskId, setTaskIdState] = useState<string | null>(null);

  // Lazy init on first render to avoid generating a UUID on the server.
  useEffect(() => {
    const existing = readFromStorage<string>(STORAGE_KEY);
    const initialized = existing ?? generateUuidV4();
    if (!existing) writeToStorage(STORAGE_KEY, initialized);
    setSessionId(initialized);
    setStudyIdState(readFromStorage<string>(STUDY_ID_STORAGE_KEY));
    setConditionState(readFromStorage<string>(CONDITION_STORAGE_KEY));
    setTaskIdState(readFromStorage<string>(TASK_ID_STORAGE_KEY));
  }, []);

  function enroll(id: string): void {
    writeToStorage(STUDY_ID_STORAGE_KEY, id);
    setStudyIdState(id);
  }

  function setCondition(c: string): void {
    writeToStorage(CONDITION_STORAGE_KEY, c);
    setConditionState(c);
  }

  function setTaskId(t: string): void {
    writeToStorage(TASK_ID_STORAGE_KEY, t);
    setTaskIdState(t);
  }

  function clear(): void {
    writeToStorage(STORAGE_KEY, null);
    writeToStorage(STUDY_ID_STORAGE_KEY, null);
    writeToStorage(CONDITION_STORAGE_KEY, null);
    writeToStorage(TASK_ID_STORAGE_KEY, null);
    setSessionId('');
    setStudyIdState(null);
    setConditionState(null);
    setTaskIdState(null);
  }

  return {
    sessionId,
    studyId,
    condition,
    taskId,
    enroll,
    setCondition,
    setTaskId,
    clear,
  };
}
