# Phase 2 Frontend Implementation Guide

**Generated:** 2026-05-07 (rev. 2 — security + UX + architecture fixes applied)  
**Based on:** `SPEC.md` v2.1 + existing codebase patterns  
**Goal:** Implement auth, dashboard, review, and share pages for CodeScope Phase 2

---

## Decisions Made


| Question             | Choice                                                                                          |
| -------------------- | ----------------------------------------------------------------------------------------------- |
| Auth library         | `lib/supabase.ts` — existing Supabase client with `signUp`, `signIn`, `signOut`, `getAuthToken` |
| Auth pages style     | Dark full-page centered card (matches tracer page: `#0d1117` background, GitHub-style)          |
| Save button location | Tracer page top bar (between brand and Trace button)                                            |
| Share page behavior  | Full tracer — visitor can edit and re-trace code                                                |
| Dashboard auth       | No demo mode — always requires login, redirects to `/auth/login` if unauthenticated             |
| Review replay        | Auto-play animation on load, rating buttons appear after animation completes                    |
| Review page API      | Dedicated `GET /api/review/{card_id}` endpoint (not dashboard's bulk endpoint)                  |


---

## What Changed in rev. 2


| #   | Issue                                                         | Fix Applied                                           |
| --- | ------------------------------------------------------------- | ----------------------------------------------------- |
| S1  | `SupabaseListener` was a no-op                                | Makes router refresh on auth changes                  |
| S2  | `authFetch` silently returns even on 401                      | Throws `Error("AUTH_REQUIRED")` on 401                |
| S3  | No payload size limit on saveTrace                            | `max_length=5000` enforced                            |
| S4  | JWT decoded without verification                              | Explicit warning + comment added                      |
| A1  | `fetchSharedTrace` return type broken                         | Typed correctly as `SharedTraceData`                  |
| A2  | Review page called `fetchDueReviews()` (all cards)            | Dedicated `fetchReviewCard(cardId)` added             |
| A3  | Dashboard `/api/traces` returns `{traces, due_cards, streak}` | Guide says `GET /dashboard` returns dashboard summary |
| U1  | Save button has no loading/success feedback                   | Added `saving` state + inline success message         |
| U2  | Submit review has no loading state                            | Added `submitting` state on rating button             |
| U3  | Cross-tab auth broken (no router refresh)                     | `SupabaseListener` calls `router.refresh()`           |
| B1  | `POST /api/traces/{id}/share` only had `pass`                 | Full stub with `secrets.token_hex(16)`                |


---

## Files to Create (9 files total)

### Auth Pages (3 files)

```
frontend/app/auth/login/page.tsx
frontend/app/auth/signup/page.tsx
frontend/app/auth/callback/route.ts
```

### Dashboard & Review (3 files)

```
frontend/app/dashboard/page.tsx
frontend/app/dashboard/page.module.css
frontend/app/review/[card_id]/page.tsx
```

### Share Page (1 file)

```
frontend/app/trace/[share_token]/page.tsx
```

### New/Modified API Lib (2 files)

```
frontend/lib/api.ts          (ADD new functions, do NOT remove existing ones)
frontend/types/user.ts      (NEW — User and Session types)
```

---

## Implementation Order (strict order — each step depends on the previous)

---

## Step 1 — `frontend/types/user.ts` (NEW FILE)

**Why first:** Every other file needs these types. Create this before anything else.

```typescript
// frontend/types/user.ts

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
  next_review_date: string;  // ISO date string "YYYY-MM-DD" — string, NOT Date
  interval_days: number;
  easiness_factor: number;
  repetitions: number;
  due: boolean;
  trace?: SavedTrace & { steps: TraceStep[] };  // joined trace data
}

export interface DashboardData {
  traces: SavedTrace[];
  due_cards: ReviewCard[];
  streak: number;
  total_traces: number;
}

export interface SaveTraceResponse {
  id: string;
  share_token: string;
  created_at: string;
}

/** Single review card — returned by GET /api/review/{card_id} */
export interface ReviewCardDetail {
  id: string;
  trace_id: string;
  concept_tag: string;
  next_review_date: string;
  interval_days: number;
  easiness_factor: number;
  repetitions: number;
  trace: SavedTrace & { steps: TraceStep[] };
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
  steps: TraceStep[];  // included when loading from DB
}
```

**Key decisions:**

- `next_review_date` is a **string** ("2026-05-08"), NOT a Date object
- `ReviewCardDetail.trace` includes `steps` — the review page gets everything it needs in one call
- `SharedTraceData.steps` is always present when loaded from the backend

---

## Step 2 — `frontend/lib/api.ts` (ADD functions, do NOT remove existing ones)

**IMPORTANT:** Add these functions to the existing `api.ts`. Do NOT replace existing `runTrace` and `explainLine`.

```typescript
// ADD TO frontend/lib/api.ts

// ── Auth helper ──────────────────────────────────────────────────────
async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = await getAuthToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, { ...options, headers });

  // ALWAYS throw AUTH_REQUIRED on 401 — do not silently return the response
  if (res.status === 401) {
    throw new Error("AUTH_REQUIRED");
  }

  return res;
}

// ── Dashboard ───────────────────────────────────────────────────────

/**
 * Fetch dashboard summary: traces list + due cards + streak.
 * Calls GET /api/dashboard (aggregated endpoint — one call, not two).
 */
export async function fetchDashboard(): Promise<DashboardData> {
  const res = await authFetch(`${API_BASE}/api/dashboard`);
  if (res.status === 401) throw new Error("AUTH_REQUIRED");
  if (!res.ok) throw new Error(`Failed to load dashboard: ${res.status}`);
  return res.json();
}

/**
 * Save a trace to the user's account.
 * Payload max: code ≤ 5000 chars, steps ≤ 500 steps.
 */
export async function saveTrace(params: {
  code: string;
  language?: string;
  steps: import("@/types/trace").TraceStep[];
  concept_tags?: string[];
}): Promise<SaveTraceResponse> {
  if (params.code.length > 5000) {
    throw new Error("Code exceeds 5000 character limit");
  }
  const res = await authFetch(`${API_BASE}/api/traces`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code: params.code,
      language: params.language ?? "python",
      steps: params.steps,
      concept_tags: params.concept_tags ?? [],
    }),
  });
  if (res.status === 401) throw new Error("AUTH_REQUIRED");
  if (res.status === 402) throw new Error("UPGRADE_REQUIRED");
  if (!res.ok) throw new Error(`Failed to save trace: ${res.status}`);
  return res.json();
}

// ── Review ──────────────────────────────────────────────────────────

/**
 * Fetch a single review card with its full trace + steps.
 * This is the correct API for the /review/[card_id] page.
 * Calls GET /api/review/{card_id} — NOT fetchDueReviews().
 */
export async function fetchReviewCard(cardId: string): Promise<ReviewCardDetail> {
  const res = await authFetch(`${API_BASE}/api/review/${cardId}`);
  if (res.status === 401) throw new Error("AUTH_REQUIRED");
  if (res.status === 404) throw new Error("CARD_NOT_FOUND");
  if (!res.ok) throw new Error(`Failed to load review card: ${res.status}`);
  return res.json();
}

/**
 * Submit a review rating.
 * rating: "again" | "hard" | "good" | "easy"
 */
export async function submitReviewRating(
  cardId: string,
  rating: "again" | "hard" | "good" | "easy"
): Promise<{ next_review_date: string; new_interval_days: number }> {
  const res = await authFetch(`${API_BASE}/api/review/${cardId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  });
  if (res.status === 401) throw new Error("AUTH_REQUIRED");
  if (!res.ok) throw new Error(`Failed to submit review: ${res.status}`);
  return res.json();
}

// ── Shared trace ─────────────────────────────────────────────────────

/**
 * Get a trace by its share token (public endpoint — no auth needed).
 * Steps are included in the response.
 */
export async function fetchSharedTrace(shareToken: string): Promise<SharedTraceData> {
  const res = await fetch(`${API_BASE}/api/traces/shared/${shareToken}`);
  if (res.status === 404) throw new Error("TRACE_NOT_FOUND");
  if (!res.ok) throw new Error(`Failed to load trace: ${res.status}`);
  return res.json();
}

/**
 * Generate or update a share link for a trace.
 * Requires authentication.
 */
export async function shareTrace(traceId: string): Promise<{ share_token: string; share_url: string }> {
  const res = await authFetch(`${API_BASE}/api/traces/${traceId}/share`, {
    method: "POST",
  });
  if (res.status === 401) throw new Error("AUTH_REQUIRED");
  if (!res.ok) throw new Error(`Failed to share trace: ${res.status}`);
  return res.json();
}
```

---

## Step 3 — `frontend/app/auth/login/page.tsx` (NEW FILE)

```typescript
// frontend/app/auth/login/page.tsx
"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signIn, getSupabase } from "@/lib/supabase";
import styles from "../auth.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const { data: { session } } = getSupabase().auth.getSession();
    if (session) router.replace("/dashboard");
  }, [router]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signIn(email, password);
      router.push("/dashboard");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Login failed";
      if (msg.includes("Invalid login credentials")) {
        setError("Invalid email or password. Please try again.");
      } else if (msg.includes("Email not confirmed")) {
        setError("Email not confirmed. Check your inbox for a confirmation email.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [email, password, router]);

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </div>
        <h1 className={styles.title}>Sign in to your account</h1>
        <p className={styles.subtitle}>
          New here?{" "}
          <Link href="/auth/signup" className={styles.link}>Create an account</Link>
        </p>
        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label htmlFor="email" className={styles.label}>Email</label>
            <input
              id="email" type="email" value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com" required autoComplete="email"
              className={styles.input}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="password" className={styles.label}>Password</label>
            <input
              id="password" type="password" value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password" required autoComplete="current-password"
              className={styles.input}
            />
          </div>
          {error && <div className={styles.error}><span>⚠</span> {error}</div>}
          <button
            type="submit" disabled={loading || !email || !password}
            className={styles.submitBtn}
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <p className={styles.footer}>
          <Link href="/" className={styles.link}>← Back to tracer</Link>
        </p>
      </div>
    </div>
  );
}
```

---

## Step 4 — `frontend/app/auth/signup/page.tsx` (NEW FILE)

```typescript
// frontend/app/auth/signup/page.tsx
"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signUp, getSupabase } from "@/lib/supabase";
import styles from "../auth.module.css";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    const { data: { session } } = getSupabase().auth.getSession();
    if (session) router.replace("/dashboard");
  }, [router]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 6) { setError("Password must be at least 6 characters."); return; }
    if (password !== confirmPassword) { setError("Passwords do not match."); return; }
    setLoading(true);
    try {
      const data = await signUp(email, password);
      if (data.user && !data.session) {
        setSuccessMessage(
          "Account created! Check your email to confirm your account before signing in."
        );
      } else {
        router.push("/dashboard");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Sign up failed";
      if (msg.includes("already registered")) {
        setError("An account with this email already exists.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [email, password, confirmPassword, router]);

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </div>
        <h1 className={styles.title}>Create your account</h1>
        <p className={styles.subtitle}>
          Already have an account?{" "}
          <Link href="/auth/login" className={styles.link}>Sign in</Link>
        </p>

        {successMessage ? (
          <div className={styles.success}>
            <span>✓</span> {successMessage}
            <p className={styles.successBack}>
              <Link href="/auth/login" className={styles.link}>← Back to sign in</Link>
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className={styles.form}>
            <div className={styles.field}>
              <label htmlFor="email" className={styles.label}>Email</label>
              <input
                id="email" type="email" value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com" required autoComplete="email"
                className={styles.input}
              />
            </div>
            <div className={styles.field}>
              <label htmlFor="password" className={styles.label}>Password</label>
              <input
                id="password" type="password" value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters" required minLength={6}
                autoComplete="new-password" className={styles.input}
              />
            </div>
            <div className={styles.field}>
              <label htmlFor="confirmPassword" className={styles.label}>Confirm password</label>
              <input
                id="confirmPassword" type="password" value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Repeat your password" required autoComplete="new-password"
                className={styles.input}
              />
            </div>
            {error && <div className={styles.error}><span>⚠</span> {error}</div>}
            <button
              type="submit" disabled={loading || !email || !password || !confirmPassword}
              className={styles.submitBtn}
            >
              {loading ? "Creating account..." : "Create account"}
            </button>
          </form>
        )}
        <p className={styles.footer}>
          <Link href="/" className={styles.link}>← Back to tracer</Link>
        </p>
      </div>
    </div>
  );
}
```

---

## Step 5 — `frontend/app/auth/auth.module.css` (NEW FILE — shared by login and signup)

Create in `frontend/app/auth/` so both pages import from the same file.

```css
/* frontend/app/auth/auth.module.css */

.page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0d1117;
  padding: 20px;
}

.card {
  width: 100%;
  max-width: 400px;
  background: #161b22;
  border: 1px solid #21262d;
  border-radius: 12px;
  padding: 40px;
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

.brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 28px;
}

.logo { font-size: 24px; color: #58a6ff; }
.brandName { font-size: 18px; font-weight: 700; color: #e6edf3; }

.title {
  font-size: 20px;
  font-weight: 700;
  color: #e6edf3;
  text-align: center;
  margin: 0 0 8px;
}

.subtitle {
  font-size: 13px;
  color: #8b949e;
  text-align: center;
  margin: 0 0 28px;
}

.form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.label { font-size: 13px; font-weight: 600; color: #e6edf3; }

.input {
  padding: 10px 12px;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  color: #e6edf3;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s;
}
.input::placeholder { color: #484f58; }
.input:focus {
  border-color: #388bfd;
  box-shadow: 0 0 0 3px rgba(56, 139, 253, 0.15);
}

.error {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px;
  background: rgba(248, 81, 73, 0.1);
  border: 1px solid rgba(248, 81, 73, 0.3);
  border-radius: 6px; color: #f85149; font-size: 13px;
}

.success {
  display: flex; flex-direction: column; gap: 12px;
  padding: 14px 16px;
  background: rgba(35, 134, 54, 0.1);
  border: 1px solid rgba(35, 134, 54, 0.3);
  border-radius: 6px; color: #3fb950; font-size: 13px; margin-bottom: 16px;
}
.successBack { margin: 0; color: #8b949e; }

.submitBtn {
  margin-top: 4px; padding: 10px 20px;
  background: linear-gradient(135deg, #1f6feb, #388bfd);
  border: none; border-radius: 6px; color: white;
  font-size: 14px; font-weight: 600; font-family: inherit;
  cursor: pointer; transition: all 0.15s;
}
.submitBtn:hover:not(:disabled) {
  background: linear-gradient(135deg, #388bfd, #58a6ff);
  transform: translateY(-1px);
}
.submitBtn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

.link { color: #58a6ff; text-decoration: none; font-weight: 500; }
.link:hover { text-decoration: underline; }
.footer { margin-top: 20px; text-align: center; font-size: 13px; color: #8b949e; }
```

---

## Step 6 — `frontend/app/auth/callback/route.ts` (NEW FILE — Next.js Route Handler)

```typescript
// frontend/app/auth/callback/route.ts
import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/dashboard";

  if (code) {
    const supabase = getSupabase();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  return NextResponse.redirect(`${origin}/auth/login?error=auth_callback_failed`);
}
```

---

## Step 7 — `frontend/app/dashboard/page.tsx` (NEW FILE)

```typescript
// frontend/app/dashboard/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getSupabase } from "@/lib/supabase";
import { fetchDashboard } from "@/lib/api";
import { formatNextReview } from "@/lib/sm2";
import type { SavedTrace, ReviewCard } from "@/types/user";
import styles from "./page.module.css";

function truncateCode(code: string, maxLines = 4): string {
  return code.split("\n").filter((l) => l.trim()).slice(0, maxLines).join("\n");
}

function timeAgo(dateStr: string): string {
  const diffDays = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return `${Math.floor(diffDays / 30)}mo ago`;
}

export default function DashboardPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [traces, setTraces] = useState<SavedTrace[]>([]);
  const [dueCards, setDueCards] = useState<ReviewCard[]>([]);
  const [streak, setStreak] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const { data: { session } } = getSupabase().auth.getSession();
      if (!session) { router.replace("/auth/login"); return; }
      setUserEmail(session.user.email ?? null);

      try {
        // Single call — returns {traces, due_cards, streak, total_traces}
        const data = await fetchDashboard();
        setTraces(data.traces);
        setDueCards(data.due_cards);
        setStreak(data.streak);
      } catch (err) {
        if (err instanceof Error && err.message === "AUTH_REQUIRED") {
          router.replace("/auth/login"); return;
        }
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  const handleSignOut = useCallback(async () => {
    const { signOut } = await import("@/lib/supabase");
    await signOut();
    router.replace("/auth/login");
  }, [router]);

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.loading}>
          <span className={styles.spinner}>◈</span> Loading dashboard...
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Link href="/" className={styles.brandLink}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </Link>
        <div className={styles.actions}>
          <Link href="/" className={styles.newTraceBtn}>+ New Trace</Link>
          <div className={styles.userMenu}>
            <span className={styles.userEmail}>{userEmail}</span>
            <button onClick={handleSignOut} className={styles.signOutBtn}>Sign out</button>
          </div>
        </div>
      </header>

      <main className={styles.main}>
        {error && (
          <div className={styles.errorBanner}><span>⚠</span> {error}</div>
        )}

        {/* Saved Traces */}
        <section>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>My Traces</h2>
            <span className={styles.count}>{traces.length} saved</span>
          </div>

          {traces.length === 0 ? (
            <div className={styles.emptyState}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#484f58" strokeWidth="1.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              <p>No traces saved yet.</p>
              <p className={styles.emptyHint}>
                Paste a function and click "Save" to get started.
              </p>
            </div>
          ) : (
            <div className={styles.traceGrid}>
              {traces.map((trace) => (
                <div key={trace.id} className={styles.traceCard}>
                  <pre className={styles.codePreview}>
                    <code>{truncateCode(trace.code)}</code>
                  </pre>
                  <div className={styles.traceTags}>
                    {trace.concept_tags.slice(0, 3).map((tag) => (
                      <span key={tag} className={styles.tag}>{tag}</span>
                    ))}
                  </div>
                  <div className={styles.traceFooter}>
                    <span className={styles.traceDate}>{timeAgo(trace.created_at)}</span>
                    <div className={styles.traceActions}>
                      <Link href={`/trace/${trace.share_token}`} className={styles.actionBtn}>Open</Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Review Queue */}
        <section>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Review Queue</h2>
            <div className={styles.streakBadge}>
              {streak > 0 ? `🔥 ${streak}-day streak` : "Start your streak!"}
            </div>
          </div>

          {dueCards.length === 0 ? (
            <div className={styles.emptyState}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#484f58" strokeWidth="1.5">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
              </svg>
              <p>No reviews due.</p>
              <p className={styles.emptyHint}>Trace some code to build your review queue.</p>
            </div>
          ) : (
            <div className={styles.cardGrid}>
              {dueCards.map((card) => (
                <div key={card.id} className={styles.reviewCard}>
                  <div className={styles.reviewCardHeader}>
                    <span className={styles.conceptTag}>{card.concept_tag}</span>
                    <span className={styles.dueLabel}>
                      {formatNextReview(new Date(card.next_review_date))}
                    </span>
                  </div>
                  <div className={styles.reviewCardMeta}>
                    {card.interval_days === 1 ? "New card" : `Reviewed ${card.repetitions}×`}
                  </div>
                  <Link href={`/review/${card.id}`} className={styles.reviewBtn}>Review Now</Link>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
```

---

## Step 8 — `frontend/app/dashboard/page.module.css` (NEW FILE)

```css
/* frontend/app/dashboard/page.module.css */

.page { min-height: 100vh; background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

.loading { display: flex; align-items: center; justify-content: center; min-height: 100vh; gap: 12px; color: #8b949e; font-size: 14px; }
.spinner { animation: spin 1s linear infinite; color: #58a6ff; font-size: 20px; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.topBar { display: flex; align-items: center; justify-content: space-between; padding: 0 24px; height: 56px; border-bottom: 1px solid #21262d; background: #161b22; }
.brandLink { display: flex; align-items: center; gap: 8px; text-decoration: none; }
.logo { font-size: 20px; color: #58a6ff; }
.brandName { font-size: 16px; font-weight: 700; color: #e6edf3; }
.actions { display: flex; align-items: center; gap: 16px; }

.newTraceBtn { padding: 8px 16px; background: linear-gradient(135deg, #1f6feb, #388bfd); border-radius: 6px; color: white; font-size: 13px; font-weight: 600; text-decoration: none; transition: all 0.15s; }
.newTraceBtn:hover { background: linear-gradient(135deg, #388bfd, #58a6ff); transform: translateY(-1px); }
.userMenu { display: flex; align-items: center; gap: 12px; }
.userEmail { font-size: 13px; color: #8b949e; }
.signOutBtn { padding: 6px 12px; background: transparent; border: 1px solid #30363d; border-radius: 6px; color: #8b949e; font-size: 12px; font-family: inherit; cursor: pointer; transition: all 0.15s; }
.signOutBtn:hover { background: #21262d; color: #e6edf3; }

.main { max-width: 1100px; margin: 0 auto; padding: 32px 24px; display: flex; flex-direction: column; gap: 40px; }

.errorBanner { display: flex; align-items: center; gap: 8px; padding: 12px 16px; background: rgba(248,81,73,0.1); border: 1px solid rgba(248,81,73,0.3); border-radius: 8px; color: #f85149; font-size: 13px; }

.sectionHeader { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.sectionTitle { font-size: 18px; font-weight: 700; color: #e6edf3; margin: 0; }
.count { font-size: 13px; color: #8b949e; }
.streakBadge { font-size: 13px; font-weight: 600; color: #f59e0b; }

.emptyState { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 60px 20px; background: #161b22; border: 1px solid #21262d; border-radius: 12px; text-align: center; }
.emptyState p { margin: 0; color: #8b949e; font-size: 14px; }
.emptyHint { font-size: 13px !important; color: #484f58 !important; }

.traceGrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.traceCard { background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 16px; display: flex; flex-direction: column; gap: 10px; transition: border-color 0.15s; }
.traceCard:hover { border-color: #30363d; }
.codePreview { background: #0d1117; border-radius: 6px; padding: 10px 12px; margin: 0; overflow: hidden; }
.codePreview code { font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace; font-size: 11px; color: #8b949e; white-space: pre; display: block; max-height: 80px; overflow: hidden; }
.traceTags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { padding: 2px 8px; background: rgba(88,166,255,0.1); border: 1px solid rgba(88,166,255,0.2); border-radius: 12px; font-size: 11px; color: #58a6ff; }
.traceFooter { display: flex; align-items: center; justify-content: space-between; }
.traceDate { font-size: 12px; color: #484f58; }
.traceActions { display: flex; gap: 6px; }
.actionBtn { padding: 4px 10px; background: #21262d; border-radius: 4px; color: #e6edf3; font-size: 12px; font-weight: 500; text-decoration: none; transition: background 0.15s; }
.actionBtn:hover { background: #30363d; }

.cardGrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
.reviewCard { background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 16px; display: flex; flex-direction: column; gap: 8px; transition: border-color 0.15s; }
.reviewCard:hover { border-color: #30363d; }
.reviewCardHeader { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.conceptTag { font-size: 13px; font-weight: 600; color: #e6edf3; }
.dueLabel { font-size: 12px; color: #f59e0b; font-weight: 500; }
.reviewCardMeta { font-size: 12px; color: #484f58; }
.reviewBtn { margin-top: 4px; padding: 7px 14px; background: linear-gradient(135deg, #1f6feb, #388bfd); border-radius: 6px; color: white; font-size: 13px; font-weight: 600; text-decoration: none; text-align: center; transition: all 0.15s; }
.reviewBtn:hover { background: linear-gradient(135deg, #388bfd, #58a6ff); transform: translateY(-1px); }
```

---

## Step 9 — `frontend/app/review/[card_id]/page.tsx` (NEW FILE)

**CRITICAL CHANGE:** This page now calls `fetchReviewCard(cardId)` which returns the full trace with steps in one call. The animation plays automatically. Rating has a loading state.

```typescript
// frontend/app/review/[card_id]/page.tsx
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { getSupabase } from "@/lib/supabase";
import { fetchReviewCard, submitReviewRating } from "@/lib/api";
import { formatNextReview } from "@/lib/sm2";
import type { ReviewCardDetail } from "@/types/user";
import type { TraceStep } from "@/types/trace";
import styles from "./review.module.css";

const CodeEditor = dynamic(
  () => import("@/components/editor/CodeEditor").then((m) => m.CodeEditor),
  { ssr: false, loading: () => <div className={styles.editorLoading}>Loading code...</div> }
);

type ReviewState = "loading" | "playing" | "rating" | "submitting" | "submitted" | "error";
const INTERVAL_MS = 750;

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const cardId = params.card_id as string;

  const [card, setCard] = useState<ReviewCardDetail | null>(null);
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [currentStep, setCurrentStep] = useState(0);
  const [reviewState, setReviewState] = useState<ReviewState>("loading");
  const [rating, setRating] = useState<"again" | "hard" | "good" | "easy" | null>(null);
  const [nextReview, setNextReview] = useState<string | null>(null);
  const [nextInterval, setNextInterval] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rafRef = useRef<number | null>(null);
  const lastTimestampRef = useRef<number | null>(null);
  const playingRef = useRef(false);

  // Load single card with trace + steps in one API call
  useEffect(() => {
    async function load() {
      const { data: { session } } = getSupabase().auth.getSession();
      if (!session) { router.replace("/auth/login"); return; }
      try {
        const data = await fetchReviewCard(cardId);
        setCard(data);
        setSteps(data.trace.steps ?? []);
        setReviewState("playing");
      } catch (err) {
        if (err instanceof Error && err.message === "CARD_NOT_FOUND") {
          setError("Card not found. It may have already been reviewed.");
        } else if (err instanceof Error && err.message === "AUTH_REQUIRED") {
          router.replace("/auth/login");
        } else {
          setError(err instanceof Error ? err.message : "Failed to load card");
        }
        setReviewState("error");
      }
    }
    load();
  }, [cardId, router]);

  // Auto-play animation
  const startAnimation = useCallback((stepsToPlay: TraceStep[]) => {
    if (stepsToPlay.length === 0) { setReviewState("rating"); return; }
    playingRef.current = true;
    setCurrentStep(0);

    function tick(timestamp: number) {
      if (!playingRef.current) return;
      if (lastTimestampRef.current === null) lastTimestampRef.current = timestamp;
      const elapsed = timestamp - lastTimestampRef.current;

      if (elapsed >= INTERVAL_MS) {
        setCurrentStep((prev) => {
          if (prev + 1 >= stepsToPlay.length) {
            playingRef.current = false;
            lastTimestampRef.current = null;
            setReviewState("rating");
            return prev;
          }
          lastTimestampRef.current = timestamp;
          return prev + 1;
        });
        return;
      }
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
  }, []);

  // Trigger auto-play once card loads
  useEffect(() => {
    if (reviewState !== "playing") return;
    const timer = setTimeout(() => {
      startAnimation(steps.length > 0 ? steps : []);
    }, 800);
    return () => clearTimeout(timer);
  }, [reviewState]);

  // Cleanup rAF on unmount
  useEffect(() => {
    return () => {
      playingRef.current = false;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const handleRating = useCallback(async (r: "again" | "hard" | "good" | "easy") => {
    setRating(r);
    setReviewState("submitting");
    try {
      const result = await submitReviewRating(cardId, r);
      setNextReview(result.next_review_date);
      setNextInterval(result.new_interval_days);
      setReviewState("submitted");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit review");
      setReviewState("rating"); // return to rating so user can retry
    }
  }, [cardId]);

  if (reviewState === "loading") {
    return <div className={styles.page}><div className={styles.loading}><span className={styles.spinner}>◈</span> Loading review...</div></div>;
  }

  if (reviewState === "error") {
    return (
      <div className={styles.page}>
        <div className={styles.errorState}>
          <p>⚠ {error}</p>
          <Link href="/dashboard" className={styles.backBtn}>← Back to dashboard</Link>
        </div>
      </div>
    );
  }

  const currentStepData = steps[currentStep] ?? null;

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Link href="/dashboard" className={styles.backLink}>← Dashboard</Link>
        <div className={styles.cardInfo}>
          {card && <span className={styles.conceptTag}>{card.concept_tag}</span>}
        </div>
        <div />
      </header>

      <main className={styles.main}>
        <div className={styles.editorSection}>
          {card ? (
            <CodeEditor
              code={card.trace.code}
              onChange={() => {}}
              currentLine={currentStepData?.line_number ?? 1}
              readOnly
            />
          ) : (
            <div className={styles.noCode}>
              <p>Trace code unavailable.</p>
              <p className={styles.hint}>The trace may have been deleted.</p>
            </div>
          )}
        </div>

        {reviewState === "playing" && steps.length > 0 && (
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }} />
          </div>
        )}

        {(reviewState === "rating" || reviewState === "submitting") && (
          <div className={styles.ratingPanel}>
            <h2 className={styles.ratingTitle}>
              {reviewState === "submitting" ? "Submitting..." : "How well did you understand this?"}
            </h2>
            <div className={styles.ratingButtons}>
              {(["again", "hard", "good", "easy"] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => handleRating(r)}
                  disabled={reviewState === "submitting" || rating !== null}
                  className={`${styles.ratingBtn} ${styles[`ratingBtn_${r}`]}`}
                >
                  <span className={styles.ratingLabel}>
                    {r === "again" ? "Again" : r === "hard" ? "Hard" : r === "good" ? "Good" : "Easy"}
                  </span>
                  <span className={styles.ratingHint}>
                    {r === "again" ? "Forgot it" : r === "hard" ? "Struggled" : r === "good" ? "Got it" : "Too easy"}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {reviewState === "submitted" && (
          <div className={styles.submittedPanel}>
            <div className={styles.submittedIcon}>✓</div>
            <h2 className={styles.submittedTitle}>Review complete!</h2>
            {nextReview && nextInterval !== null && (
              <p className={styles.submittedInfo}>
                Next review: <strong>{formatNextReview(new Date(nextReview))}</strong>
                {" "}({nextInterval === 1 ? "1 day" : `${nextInterval} days`})
              </p>
            )}
            <button onClick={() => router.push("/dashboard")} className={styles.dashboardBtn}>
              ← Back to Dashboard
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
```

---

## Step 9b — `frontend/app/review/[card_id]/review.module.css` (NEW FILE)

```css
/* frontend/app/review/[card_id]/review.module.css */

.page { min-height: 100vh; background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; display: flex; flex-direction: column; }

.loading, .errorState { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; gap: 12px; color: #8b949e; font-size: 14px; }
.spinner { animation: spin 1s linear infinite; color: #58a6ff; font-size: 20px; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.topBar { display: flex; align-items: center; justify-content: space-between; padding: 0 20px; height: 56px; border-bottom: 1px solid #21262d; background: #161b22; }
.backLink { font-size: 13px; color: #8b949e; text-decoration: none; transition: color 0.15s; }
.backLink:hover { color: #e6edf3; }
.cardInfo { display: flex; align-items: center; gap: 12px; }
.conceptTag { padding: 4px 12px; background: rgba(88,166,255,0.1); border: 1px solid rgba(88,166,255,0.2); border-radius: 16px; font-size: 13px; font-weight: 600; color: #58a6ff; }

.main { flex: 1; display: flex; flex-direction: column; }
.editorSection { flex: 1; overflow: hidden; border-bottom: 1px solid #21262d; }
.editorLoading, .noCode { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 8px; color: #484f58; font-size: 13px; }
.hint { color: #30363d; }

.progressBar { height: 3px; background: #21262d; flex-shrink: 0; }
.progressFill { height: 100%; background: linear-gradient(90deg, #1f6feb, #388bfd); transition: width 0.1s linear; }

.ratingPanel { padding: 32px 24px; background: #161b22; border-top: 1px solid #21262d; display: flex; flex-direction: column; align-items: center; gap: 20px; animation: slideUp 0.2s ease-out; }
@keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
.ratingTitle { font-size: 16px; font-weight: 600; color: #e6edf3; margin: 0; }
.ratingButtons { display: flex; gap: 12px; }
.ratingBtn { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 14px 28px; border-radius: 10px; border: 1px solid; font-family: inherit; cursor: pointer; transition: all 0.15s; }
.ratingBtn:disabled { opacity: 0.6; cursor: not-allowed; }
.ratingLabel { font-size: 14px; font-weight: 700; }
.ratingHint { font-size: 11px; opacity: 0.7; }
.ratingBtn_again { background: rgba(248,81,73,0.1); border-color: rgba(248,81,73,0.3); color: #f85149; }
.ratingBtn_again:hover:not(:disabled) { background: rgba(248,81,73,0.2); }
.ratingBtn_hard { background: rgba(245,158,11,0.1); border-color: rgba(245,158,11,0.3); color: #f59e0b; }
.ratingBtn_hard:hover:not(:disabled) { background: rgba(245,158,11,0.2); }
.ratingBtn_good { background: rgba(35,134,54,0.1); border-color: rgba(35,134,54,0.3); color: #3fb950; }
.ratingBtn_good:hover:not(:disabled) { background: rgba(35,134,54,0.2); }
.ratingBtn_easy { background: rgba(88,166,255,0.1); border-color: rgba(88,166,255,0.3); color: #58a6ff; }
.ratingBtn_easy:hover:not(:disabled) { background: rgba(88,166,255,0.2); }

.submittedPanel { padding: 48px 24px; background: #161b22; border-top: 1px solid #21262d; display: flex; flex-direction: column; align-items: center; gap: 16px; animation: slideUp 0.2s ease-out; }
.submittedIcon { width: 56px; height: 56px; border-radius: 50%; background: rgba(35,134,54,0.15); border: 2px solid #3fb950; display: flex; align-items: center; justify-content: center; font-size: 24px; color: #3fb950; }
.submittedTitle { font-size: 20px; font-weight: 700; color: #e6edf3; margin: 0; }
.submittedInfo { font-size: 14px; color: #8b949e; margin: 0; }
.dashboardBtn { margin-top: 8px; padding: 10px 20px; background: #21262d; border: 1px solid #30363d; border-radius: 6px; color: #e6edf3; font-size: 14px; font-family: inherit; cursor: pointer; transition: all 0.15s; }
.dashboardBtn:hover { background: #30363d; }
.backBtn { color: #58a6ff; text-decoration: none; font-size: 13px; }
.backBtn:hover { text-decoration: underline; }
```

---

## Step 10 — `frontend/app/trace/[share_token]/page.tsx` (NEW FILE)

```typescript
// frontend/app/trace/[share_token]/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { fetchSharedTrace, saveTrace } from "@/lib/api";
import { getSupabase } from "@/lib/supabase";
import type { SharedTraceData } from "@/types/user";
import type { TraceResult } from "@/types/trace";
import { VariablePanel } from "@/components/tracer/VariablePanel";
import { AnimationControls } from "@/components/tracer/AnimationControls";
import styles from "./share.module.css";

const CodeEditor = dynamic(
  () => import("@/components/editor/CodeEditor").then((m) => m.CodeEditor),
  { ssr: false, loading: () => <div className={styles.editorLoading}>Loading editor...</div> }
);

export default function SharedTracePage() {
  const params = useParams();
  const router = useRouter();
  const shareToken = params.share_token as string;

  const [trace, setTrace] = useState<SharedTraceData | null>(null);
  const [code, setCode] = useState("");
  const [traceResult, setTraceResult] = useState<TraceResult | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchSharedTrace(shareToken);
        setTrace(data);
        setCode(data.code);
        // Load steps if already present (from DB)
        if (data.steps?.length) {
          setTraceResult({ trace_id: data.id, steps: data.steps, total_steps: data.steps.length, duration_ms: 0 });
        }
      } catch (err) {
        if (err instanceof Error && err.message === "TRACE_NOT_FOUND") setNotFound(true);
        else setError(err instanceof Error ? err.message : "Failed to load trace");
      }
    }
    load();
  }, [shareToken]);

  const handleTrace = useCallback(async () => {
    if (!code.trim()) return;
    setIsLoading(true);
    setError(null);
    setCurrentStep(0);
    try {
      const { runTrace } = await import("@/lib/api");
      const result = await runTrace(code);
      setTraceResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run trace");
    } finally {
      setIsLoading(false);
    }
  }, [code]);

  const handleSave = useCallback(async () => {
    const { data: { session } } = getSupabase().auth.getSession();
    if (!session) { router.push("/auth/login"); return; }
    if (!traceResult?.steps?.length) { setError("Run the trace first before saving."); return; }
    setIsSaving(true);
    setError(null);
    setSaveSuccess(false);
    try {
      const result = await saveTrace({
        code,
        steps: traceResult.steps,
        concept_tags: trace?.concept_tags ?? [],
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      if (err instanceof Error && err.message === "AUTH_REQUIRED") { router.push("/auth/login"); return; }
      setError(err instanceof Error ? err.message : "Failed to save trace");
    } finally {
      setIsSaving(false);
    }
  }, [code, traceResult, trace, router]);

  if (notFound) {
    return (
      <div className={styles.page}>
        <div className={styles.notFound}>
          <h1>Trace not found</h1>
          <p>This shared trace may have been deleted or the link is invalid.</p>
          <Link href="/" className={styles.homeLink}>← Go to CodeScope</Link>
        </div>
      </div>
    );
  }

  const steps = traceResult?.steps ?? [];
  const currentStepData = steps[currentStep] ?? null;

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Link href="/" className={styles.brand}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </Link>
        <div className={styles.actions}>
          <button onClick={handleSave} disabled={!traceResult || isSaving} className={styles.saveBtn}>
            {isSaving ? "⏳ Saving..." : saveSuccess ? "✓ Saved!" : "💾 Save"}
          </button>
          <button onClick={handleTrace} disabled={isLoading || !code.trim()} className={styles.traceBtn}>
            {isLoading ? "⏳" : "▶"} Trace
          </button>
        </div>
      </header>

      {error && (
        <div className={styles.errorBanner}>
          <span>⚠</span> {error}
          <button onClick={() => setError(null)} className={styles.dismissBtn}>✕</button>
        </div>
      )}

      <main className={styles.main}>
        <div className={styles.editorPanel}>
          <CodeEditor
            code={code}
            onChange={setCode}
            currentLine={traceResult ? currentStepData?.line_number : undefined}
          />
        </div>
        <div className={styles.rightPanel}>
          <VariablePanel
            variables={currentStepData?.variables ?? {}}
            branches={currentStepData?.branches_taken ?? {}}
            isLoading={isLoading}
          />
        </div>
      </main>

      {traceResult && steps.length > 0 && (
        <footer className={styles.footer}>
          <AnimationControls
            steps={steps} currentStep={currentStep} onStepChange={setCurrentStep}
            totalSteps={steps.length} durationMs={traceResult.duration_ms}
          />
        </footer>
      )}
    </div>
  );
}
```

---

## Step 10b — `frontend/app/trace/[share_token]/share.module.css` (NEW FILE)

```css
/* frontend/app/trace/[share_token]/share.module.css */

.page { display: flex; flex-direction: column; height: 100vh; background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

.notFound { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; gap: 12px; text-align: center; padding: 20px; }
.notFound h1 { margin: 0; font-size: 24px; color: #e6edf3; }
.notFound p { margin: 0; color: #8b949e; font-size: 14px; }
.homeLink { margin-top: 8px; color: #58a6ff; text-decoration: none; font-size: 14px; }

.topBar { display: flex; align-items: center; justify-content: space-between; padding: 0 20px; height: 56px; border-bottom: 1px solid #21262d; background: #161b22; flex-shrink: 0; }
.brand { display: flex; align-items: center; gap: 8px; text-decoration: none; }
.logo { font-size: 20px; color: #58a6ff; }
.brandName { font-size: 16px; font-weight: 700; color: #e6edf3; }
.actions { display: flex; gap: 8px; }

.saveBtn { padding: 8px 16px; background: #21262d; border: 1px solid #30363d; border-radius: 6px; color: #8b949e; font-size: 13px; font-weight: 500; font-family: inherit; cursor: pointer; transition: all 0.15s; min-width: 80px; text-align: center; }
.saveBtn:hover:not(:disabled) { background: #30363d; color: #e6edf3; }
.saveBtn:disabled { opacity: 0.5; cursor: not-allowed; }

.traceBtn { padding: 8px 20px; border: none; border-radius: 6px; background: linear-gradient(135deg, #1f6feb, #388bfd); color: white; font-size: 14px; font-weight: 600; font-family: inherit; cursor: pointer; transition: all 0.15s; }
.traceBtn:hover:not(:disabled) { background: linear-gradient(135deg, #388bfd, #58a6ff); transform: translateY(-1px); }
.traceBtn:disabled { opacity: 0.5; cursor: not-allowed; }

.errorBanner { display: flex; align-items: center; gap: 10px; padding: 10px 20px; background: rgba(248,81,73,0.1); border-bottom: 1px solid rgba(248,81,73,0.2); color: #f85149; font-size: 13px; flex-shrink: 0; }
.dismissBtn { margin-left: auto; background: transparent; border: none; color: inherit; cursor: pointer; font-size: 12px; padding: 2px 6px; }

.main { display: flex; flex: 1; overflow: hidden; }
.editorPanel { flex: 6; overflow: hidden; border-right: 1px solid #21262d; }
.editorLoading { display: flex; align-items: center; justify-content: center; height: 100%; background: #0d1117; color: #484f58; font-size: 13px; }
.rightPanel { flex: 4; overflow: hidden; }
.footer { border-top: 1px solid #21262d; flex-shrink: 0; }
```

---

## Step 11 — Add Save Button to Tracer Page

Modify `frontend/app/tracer/page.tsx`:

Add to imports:

```tsx
import { getSupabase } from "@/lib/supabase";
import { saveTrace } from "@/lib/api";
```

Add before the component:

```tsx
function extractConceptTags(code: string): string[] {
  const tags: string[] = [];
  if (/def\s+\w+\(/.test(code)) tags.push("FUNCTION");
  if (/for\s/.test(code)) tags.push("LOOP");
  if (/while\s/.test(code)) tags.push("LOOP");
  if (/if\s/.test(code)) tags.push("CONDITIONAL");
  if (/class\s/.test(code)) tags.push("CLASS");
  if (/try\s|except\s/.test(code)) tags.push("EXCEPTION");
  if (/lambda\s/.test(code)) tags.push("LAMBDA");
  if (/\[.*for.*in.*\]/.test(code)) tags.push("COMPREHENSION");
  return tags.slice(0, 4);
}
```

Add state and handlers to `TracerPage`:

```tsx
const [saving, setSaving] = useState(false);
const [saveSuccess, setSaveSuccess] = useState(false);

const handleSaveTrace = useCallback(async () => {
  if (!traceResult?.steps?.length) return;
  const { data: { session } } = getSupabase().auth.getSession();
  if (!session) { router.push("/auth/login"); return; }
  setSaving(true);
  setError(null);
  setSaveSuccess(false);
  try {
    await saveTrace({
      code,
      steps: traceResult.steps,
      concept_tags: extractConceptTags(code),
    });
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  } catch (err) {
    if (err instanceof Error && err.message.includes("UPGRADE_REQUIRED")) {
      setError("Free plan limit reached. Upgrade to Pro to save more traces.");
    } else {
      setError(err instanceof Error ? err.message : "Failed to save");
    }
  } finally {
    setSaving(false);
  }
}, [code, traceResult, router]);
```

Add to the `actions` div (before the Trace button):

```tsx
<button
  onClick={handleSaveTrace}
  disabled={!traceResult || saving}
  className={styles.saveBtn}
  title={!traceResult ? "Run the trace first" : "Save this trace"}
>
  {saving ? "⏳" : saveSuccess ? "✓" : "💾"} {saving ? "Saving..." : saveSuccess ? "Saved!" : "Save"}
</button>
```

Add to `frontend/app/tracer/page.module.css`:

```css
.saveBtn {
  padding: 8px 16px; background: #21262d; border: 1px solid #30363d;
  border-radius: 6px; color: #8b949e; font-size: 13px; font-weight: 500;
  cursor: pointer; transition: all 0.15s; min-width: 80px; text-align: center;
}
.saveBtn:hover:not(:disabled) { background: #30363d; color: #e6edf3; }
.saveBtn:disabled { opacity: 0.4; cursor: not-allowed; }
```

---

## Step 12 — Update `frontend/app/layout.tsx`

Replace the file with:

```tsx
// frontend/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import { SupabaseListener } from "./supabase-provider";

export const metadata: Metadata = {
  title: "CodeScope",
  description: "Visualize Python code execution step by step",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="dark">
        <SupabaseListener />
        {children}
      </body>
    </html>
  );
}
```

---

## Step 13 — `frontend/app/supabase-provider.tsx` (NEW FILE — CRITICAL SECURITY FIX)

**Previous version was a no-op.** This version actually refreshes the Next.js router on auth changes so the UI stays in sync across tabs and after login/logout.

```typescript
// frontend/app/supabase-provider.tsx
"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getSupabase } from "@/lib/supabase";

export function SupabaseListener() {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const supabase = getSupabase();
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
      // Refresh the current route on any auth event (login, logout, token refresh)
      // This keeps the UI in sync without a full page reload
      if (event === "SIGNED_IN" || event === "SIGNED_OUT" || event === "TOKEN_REFRESHED") {
        router.refresh();
      }
    });
    return () => subscription.unsubscribe();
  }, [router, pathname]);

  return null;
}
```

---

## Step 14 — Backend: `backend/app/routers/auth.py` (NEW FILE)

**CRITICAL SECURITY NOTE:** This implementation decodes the JWT payload but does NOT cryptographically verify the signature. For MVP with a local Supabase instance this is acceptable. For production, use `supabase-py`'s built-in session verification or decode with `jwt.decode(key, options={"verify_signature": True})`.

```python
# backend/app/routers/auth.py
"""
Supabase JWT verification for protected routes.
"""
from fastapi import HTTPException, Header
from typing import Optional
import httpx


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Verify the Authorization: Bearer <token> header against Supabase /auth/v1/user.
    Raises HTTPException 401 if token is missing, invalid, or expired.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Use: Authorization: Bearer <token>",
        )

    token = authorization[7:]  # strip "Bearer "

    from app.config import Settings
    settings = Settings()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_service_key,
            },
        )

    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Authentication failed")

    return resp.json()
```

Also add to `backend/app/routers/__init__.py`:

```python
# backend/app/routers/__init__.py
from .auth import get_current_user
```

---

## Step 15 — Backend: Update `backend/app/main.py`

Register all routers. Ensure review router has the `/api/review` prefix:

```python
from app.routers.traces import router as traces_router
from app.routers.llm import router as llm_router
from app.routers.review import router as review_router
from app.routers.profiles import router as profiles_router

app.include_router(traces_router)                              # /api/traces/run, /api/traces, /api/traces/{id}/share
app.include_router(llm_router)                                # /api/llm/explain/stream
app.include_router(review_router, prefix="/api/review")       # /api/review/due, /api/review/{card_id}
app.include_router(profiles_router)                            # /api/profiles/*
```

---

## Step 16 — Backend: Update `backend/app/routers/traces.py`

Add these endpoints to the existing traces router:

```python
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional
import httpx, secrets
from app.config import Settings
from app.routers.auth import get_current_user


class DashboardResponse(BaseModel):
    traces: list
    due_cards: list
    streak: int
    total_traces: int


class TraceSaveRequest(BaseModel):
    code: str = Field(..., max_length=5000)
    language: str = "python"
    steps: list = Field(default_factory=list)
    concept_tags: list[str] = Field(default_factory=list)


@router.get("/api/dashboard")
async def get_dashboard(authorization: str = Header(None)):
    """Aggregated dashboard: traces + due cards + streak. Single call for the frontend."""
    user = await get_current_user(authorization)
    user_id = user.get("id", "")
    settings = Settings()

    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
        }

        # Fetch traces
        traces_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"user_id": f"eq.{user_id}", "select": "*", "order": "created_at.desc", "limit": "20"},
            headers=headers,
        )
        traces = traces_resp.json() if traces_resp.status_code == 200 else []

        # Fetch due cards
        today = date.today().isoformat()
        cards_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/review_cards",
            params={"user_id": f"eq.{user_id}", "next_review_date": f"lte.{today}", "select": "*"},
            headers=headers,
        )
        due_cards = cards_resp.json() if cards_resp.status_code == 200 else []

    return DashboardResponse(
        traces=traces,
        due_cards=[{**c, "due": True} for c in due_cards],
        streak=0,  # TODO: compute from review_logs table
        total_traces=len(traces),
    )


@router.post("/api/traces", status_code=201)
async def create_trace(req: TraceSaveRequest, authorization: str = Header(None)):
    """Save a trace for the authenticated user."""
    user = await get_current_user(authorization)
    user_id = user.get("id", "")
    settings = Settings()

    # Limit steps to 500 to prevent abuse
    steps_json = req.steps[:500]

    import json
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/traces",
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
                "Prefer": "return=representation",
            },
            json={
                "user_id": user_id,
                "code": req.code,
                "language": req.language,
                "steps": json.dumps(steps_json),
                "concept_tags": req.concept_tags,
            },
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail="Failed to save trace")

    data = resp.json()
    share_token = data[0].get("share_token", "") if isinstance(data, list) else data.get("share_token", "")
    return {"id": data[0]["id"] if isinstance(data, list) else data["id"], "share_token": share_token, "created_at": data[0]["created_at"] if isinstance(data, list) else data.get("created_at", "")}


@router.get("/api/traces/shared/{share_token}")
async def get_shared_trace(share_token: str):
    """Public: get a trace by share token (must be public)."""
    settings = Settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"share_token": f"eq.{share_token}", "is_public": "eq.true", "select": "*"},
            headers={"apikey": settings.supabase_service_key},
        )

    if resp.status_code != 200 or not resp.json():
        raise HTTPException(status_code=404, detail="Trace not found")

    trace = resp.json()[0]
    return trace


@router.post("/api/traces/{trace_id}/share")
async def share_trace(trace_id: str, authorization: str = Header(None)):
    """Generate or update share link for a trace."""
    user = await get_current_user(authorization)
    settings = Settings()
    new_token = secrets.token_hex(16)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.patch(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"id": f"eq.{trace_id}"},
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
                "Prefer": "return=minimal",
            },
            json={"share_token": new_token, "is_public": True},
        )

    if resp.status_code not in (200, 204):
        raise HTTPException(status_code=403, detail="Failed to update trace")

    return {"share_token": new_token, "share_url": f"/trace/{new_token}"}
```

---

## Step 17 — Backend: Update `backend/app/routers/review.py`

Replace the stub bodies with real Supabase calls. Keep the existing endpoint signatures:

```python
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.routers.auth import get_current_user
import httpx
from app.config import Settings

class TraceWithSteps(BaseModel):
    id: str
    code: str
    language: str
    steps: list  # already deserialized from JSON


class ReviewCardResponse(BaseModel):
    id: str
    trace_id: str
    concept_tag: str
    next_review_date: str
    interval_days: int
    easiness_factor: float
    repetitions: int
    due: bool
    trace: TraceWithSteps


class ReviewRatingRequest(BaseModel):
    rating: str  # "again" | "hard" | "good" | "easy"


RATING_MAP = {"again": 1, "hard": 2, "good": 3, "easy": 5}


@router.get("/api/review/due")
async def get_due_reviews(authorization: str = Header(None)):
    user = await get_current_user(authorization)
    user_id = user.get("id", "")
    settings = Settings()
    today = date.today().isoformat()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/review_cards",
            params={"user_id": f"eq.{user_id}", "next_review_date": f"lte.{today}", "select": "*"},
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
            },
        )
    cards = resp.json() if resp.status_code == 200 else []
    return {"cards": [{**c, "due": True} for c in cards], "streak": 0, "total_due": len(cards)}


@router.get("/api/review/{card_id}", response_model=ReviewCardResponse)
async def get_review_card(card_id: str, authorization: str = Header(None)):
    """
    Get a single review card with its full trace and steps.
    Called by the /review/[card_id] page — one call, full data.
    """
    user = await get_current_user(authorization)
    user_id = user.get("id", "")
    settings = Settings()

    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
        }

        # Fetch card
        card_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/review_cards",
            params={"id": f"eq.{card_id}", "user_id": f"eq.{user_id}", "select": "*"},
            headers=headers,
        )
        cards = card_resp.json() if card_resp.status_code == 200 else []
        if not cards:
            raise HTTPException(status_code=404, detail="Card not found")
        card = cards[0]

        # Fetch trace + steps
        trace_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"id": f"eq.{card['trace_id']}", "select": "*"},
            headers=headers,
        )
        trace_data = trace_resp.json()[0] if trace_resp.status_code == 200 and trace_resp.json() else {}

    import json
    steps = json.loads(trace_data.get("steps", "[]")) if trace_data.get("steps") else []

    return ReviewCardResponse(
        id=card["id"],
        trace_id=card["trace_id"],
        concept_tag=card.get("concept_tag", ""),
        next_review_date=card.get("next_review_date", ""),
        interval_days=card.get("interval_days", 1),
        easiness_factor=card.get("easiness_factor", 2.5),
        repetitions=card.get("repetitions", 0),
        due=True,
        trace={
            **trace_data,
            "steps": steps,
        },
    )


@router.post("/api/review/{card_id}")
async def submit_review(card_id: str, req: ReviewRatingRequest, authorization: str = Header(None)):
    if req.rating not in RATING_MAP:
        raise HTTPException(status_code=422, detail="Rating must be: again, hard, good, or easy")

    user = await get_current_user(authorization)
    user_id = user.get("id", "")
    quality = RATING_MAP[req.rating]
    settings = Settings()

    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
        }

        # Fetch current card
        card_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/review_cards",
            params={"id": f"eq.{card_id}", "user_id": f"eq.{user_id}", "select": "*"},
            headers=headers,
        )
        cards = card_resp.json() if card_resp.status_code == 200 else []
        if not cards:
            raise HTTPException(status_code=404, detail="Card not found")
        card = cards[0]

        new_ef, new_interval, new_reps, next_date = sm2_calculate(
            quality,
            card.get("easiness_factor", 2.5),
            card.get("interval_days", 1),
            card.get("repetitions", 0),
        )

        await client.patch(
            f"{settings.supabase_url}/rest/v1/review_cards",
            params={"id": f"eq.{card_id}"},
            headers={**headers, "Prefer": "return=minimal"},
            json={
                "easiness_factor": round(new_ef, 2),
                "interval_days": new_interval,
                "repetitions": new_reps,
                "next_review_date": next_date.isoformat(),
                "last_reviewed_at": "now()",
            },
        )

    return {
        "next_review_date": next_date.isoformat(),
        "new_interval_days": new_interval,
    }
```

---

## Environment Variables

Add to `frontend/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
```

Add to `backend/.env` if not present:

```
SUPABASE_URL=http://localhost:54321
SUPABASE_SERVICE_KEY=postgres
```

---

## Integration Checklist

### Auth Flow

- `/auth/login` — wrong credentials → error message; valid credentials → `/dashboard`
- `/auth/signup` — shows "check email" confirmation; after confirm → `/dashboard`
- Supabase callback → exchanges code → `/dashboard`
- Sign out → clears session → `/auth/login`
- Unauthenticated `/dashboard` → redirects to `/auth/login`
- Cross-tab: login in tab A → tab B automatically updates (SupabaseListener `router.refresh()`)

### Dashboard

- Single API call (`GET /api/dashboard`) returns traces + due cards + streak
- Empty states for both sections
- "+ New Trace" → `/`
- "Open" on trace card → `/trace/{share_token}`
- "Review Now" → `/review/{card_id}`
- Streak badge renders

### Review Page

- `GET /api/review/{card_id}` returns full card with trace + steps in one call
- Animation auto-plays at 750ms/step
- Progress bar fills during animation
- Rating buttons appear after animation; all 4 render correctly
- Submitting state (button text changes, disabled)
- Submit error → returns to rating state (user can retry)
- Submit success → "Review complete!" + next review date
- **CRITICAL:** `formatNextReview(new Date(nextReview))` — note `new Date()` wrapper

### Shared Trace Page

- Valid token → code + steps load
- Invalid token → "Trace not found"
- Edit + Trace → re-runs tracer
- Save: shows "Saving..." → "✓ Saved!" or error
- Save while logged out → redirects to login

### Tracer Page (modified)

- Save button in top bar
- Saving state on button
- Success feedback on save
- Disabled when no trace result
- Logged-out save → redirects to login

### Backend

- `GET /api/dashboard` returns `{traces, due_cards, streak, total_traces}`
- `POST /api/traces` enforces 5000-char code limit
- `GET /api/review/{card_id}` returns full card with trace + steps
- `POST /api/traces/{id}/share` generates new `share_token` + sets `is_public=true`

---

## Common Pitfalls to Avoid

### 1. `next_review_date` is always a string — wrap with `new Date()`

```tsx
// WRONG:
formatNextReview(card.next_review_date)
// RIGHT:
formatNextReview(new Date(card.next_review_date))
```

### 2. Auth calls use `authFetch` — it throws `AUTH_REQUIRED` on 401 automatically

Never use plain `fetch` for auth-protected endpoints. `authFetch` handles the 401 case.

### 3. `SupabaseListener` must call `router.refresh()` on auth events

Without it, tab B won't know tab A logged out. The no-op version is a security gap.

### 4. Review page calls `fetchReviewCard`, NOT `fetchDueReviews`

`fetchDueReviews` returns all cards and is for the dashboard. The review page needs one card with its trace.

### 5. Save button needs both `saving` and `saveSuccess` states

Without `saving`, users can double-submit. Without `saveSuccess`, they don't know it worked.

### 6. `authFetch` must throw on 401 — never silently return

The new version throws `Error("AUTH_REQUIRED")` on every 401. The old version just returned the response, which caused downstream code to fail silently.

---

## File Summary


| Step | File                                                | Action                            |
| ---- | --------------------------------------------------- | --------------------------------- |
| 1    | `frontend/types/user.ts`                            | **NEW**                           |
| 2    | `frontend/lib/api.ts`                               | **ADD** (keep existing functions) |
| 3    | `frontend/app/auth/login/page.tsx`                  | **NEW**                           |
| 4    | `frontend/app/auth/signup/page.tsx`                 | **NEW**                           |
| 5    | `frontend/app/auth/auth.module.css`                 | **NEW**                           |
| 6    | `frontend/app/auth/callback/route.ts`               | **NEW**                           |
| 7    | `frontend/app/dashboard/page.tsx`                   | **NEW**                           |
| 8    | `frontend/app/dashboard/page.module.css`            | **NEW**                           |
| 9    | `frontend/app/review/[card_id]/page.tsx`            | **NEW**                           |
| 9b   | `frontend/app/review/[card_id]/review.module.css`   | **NEW**                           |
| 10   | `frontend/app/trace/[share_token]/page.tsx`         | **NEW**                           |
| 10b  | `frontend/app/trace/[share_token]/share.module.css` | **NEW**                           |
| 11   | `frontend/app/tracer/page.tsx`                      | **MODIFY**                        |
| 12   | `frontend/app/tracer/page.module.css`               | **MODIFY**                        |
| 13   | `frontend/app/layout.tsx`                           | **MODIFY**                        |
| 14   | `frontend/app/supabase-provider.tsx`                | **NEW**                           |
| 15   | `backend/app/routers/auth.py`                       | **NEW**                           |
| 16   | `backend/app/main.py`                               | **MODIFY**                        |
| 17   | `backend/app/routers/traces.py`                     | **MODIFY**                        |
| 18   | `backend/app/routers/review.py`                     | **MODIFY**                        |
| 19   | `frontend/.env.local`                               | **MODIFY**                        |


**Total: 21 files — 15 new, 6 modified**