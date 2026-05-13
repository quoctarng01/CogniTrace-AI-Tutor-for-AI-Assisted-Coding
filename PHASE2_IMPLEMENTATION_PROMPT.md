# CodeScope Phase 2 — Implementation Prompt

Use this prompt verbatim to hand Phase 2 implementation to any AI. Everything it needs is here.

---

## Context

You are implementing Phase 2 of CodeScope — a Python code visualization tool. Phase 1 (backend tracer + frontend tracer page) is already complete and fully tested (23 unit tests + 6 integration tests all passing).

Read these files before starting:

- `C:\Users\quoct\codescope\SPEC.md` — full plan
- `C:\Users\quoct\codescope\frontend\app\tracer\page.tsx` — existing tracer page pattern
- `C:\Users\quoct\codescope\frontend\app\tracer\page.module.css` — existing CSS pattern
- `C:\Users\quoct\codescope\frontend\lib\supabase.ts` — existing Supabase client
- `C:\Users\quoct\codescope\frontend\lib\sm2.ts` — existing SM-2 implementation
- `C:\Users\quoct\codescope\frontend\lib\api.ts` — existing API functions
- `C:\Users\quoct\codescope\frontend\types\trace.ts` — existing trace types
- `C:\Users\quoct\codescope\frontend\components\tracer\VariablePanel.tsx` — existing component pattern
- `C:\Users\quoct\codescope\frontend\components\tracer\AnimationControls.tsx` — existing component pattern
- `C:\Users\quoct\codescope\frontend\components\editor\CodeEditor.tsx` — existing Monaco wrapper
- `C:\Users\quoct\codescope\backend\app\routers\review.py` — existing review router
- `C:\Users\quoct\codescope\backend\migrations\V001__initial_schema.sql` — DB schema

---

## Decisions Already Made (do not question these)


| Decision       | Choice                                                                                                       |
| -------------- | ------------------------------------------------------------------------------------------------------------ |
| Auth library   | `lib/supabase.ts` — use existing `signUp`, `signIn`, `signOut`, `getAuthToken`                               |
| Auth style     | Dark full-page centered card — background `#0d1117`, card `#161b22`, border `#21262d`, blue accent `#388bfd` |
| Save button    | Top bar of tracer page, between brand and Trace button                                                       |
| Share page     | Full tracer — visitor can edit code and re-trace                                                             |
| Dashboard auth | No demo mode — always requires login, redirects to `/auth/login` if unauthenticated                          |
| Review replay  | Auto-play animation on load (750ms/step), rating buttons appear after animation completes                    |
| CSS approach   | CSS Modules (`.module.css` files), same pattern as existing `page.module.css`                                |
| Type imports   | Use `import type` for TypeScript types                                                                       |
| API calls      | All auth-protected calls use `Authorization: Bearer <token>` header                                          |


---

## Color Palette (use exactly these)

```css
--bg-primary:    #0d1117   /* main page background */
--bg-card:       #161b22   /* card/panel background */
--border:        #21262d   /* borders and dividers */
--text-primary:  #e6edf3   /* main text */
--text-secondary:#8b949e   /* secondary/muted text */
--text-muted:    #484f58   /* placeholder/disabled text */
--accent-blue:   #388bfd   /* primary accent */
--accent-blue2:  #1f6feb   /* gradient start */
--accent-orange: #f59e0b   /* streak/warning */
--accent-red:    #f85149   /* error */
--accent-green:  #3fb950   /* success */
```

---

## Type System

All these types must exist before any component uses them. Create `frontend/types/user.ts` first.

```typescript
// frontend/types/user.ts

export interface SavedTrace {
  id: string;
  code: string;
  language: string;
  concept_tags: string[];
  is_public: boolean;
  share_token: string;
  created_at: string;  // ISO timestamp
}

export interface ReviewCard {
  id: string;
  trace_id: string;
  concept_tag: string;
  next_review_date: string;  // ISO date string "YYYY-MM-DD" — THIS IS A STRING, NOT A DATE OBJECT
  interval_days: number;
  easiness_factor: number;
  repetitions: number;
  due: boolean;
  trace?: SavedTrace;
}

export interface DashboardData {
  traces: SavedTrace[];
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
```

**CRITICAL TYPE RULE:** `next_review_date` is always a string like `"2026-05-10"`. When passing to `formatNextReview()`, always wrap in `new Date()`:

```typescript
// WRONG:
formatNextReview(card.next_review_date)
// RIGHT:
formatNextReview(new Date(card.next_review_date))
```

---

## File Manifest (execute in this exact order)

### NEW FILES (13 total)


| #   | File path                                           | Purpose                                  |
| --- | --------------------------------------------------- | ---------------------------------------- |
| 1   | `frontend/types/user.ts`                            | All user/trace/review types              |
| 2   | `frontend/app/auth/auth.module.css`                 | Shared CSS for login + signup            |
| 3   | `frontend/app/auth/login/page.tsx`                  | Login page                               |
| 4   | `frontend/app/auth/signup/page.tsx`                 | Signup page                              |
| 5   | `frontend/app/auth/callback/route.ts`               | Next.js route handler for OAuth callback |
| 6   | `frontend/app/dashboard/page.module.css`            | Dashboard styles                         |
| 7   | `frontend/app/dashboard/page.tsx`                   | Dashboard page                           |
| 8   | `frontend/app/review/[card_id]/review.module.css`   | Review page styles                       |
| 9   | `frontend/app/review/[card_id]/page.tsx`            | Review card page                         |
| 10  | `frontend/app/trace/[share_token]/share.module.css` | Shared trace page styles                 |
| 11  | `frontend/app/trace/[share_token]/page.tsx`         | Shared trace page                        |
| 12  | `backend/app/routers/auth.py`                       | JWT verification helper                  |
| 13  | `frontend/app/supabase-provider.tsx`                | Auth state listener component            |


### MODIFIED FILES (6 total)


| #   | File path                             | Change                                     |
| --- | ------------------------------------- | ------------------------------------------ |
| 14  | `frontend/lib/api.ts`                 | ADD new functions (keep all existing ones) |
| 15  | `frontend/app/tracer/page.tsx`        | Add Save button + handler                  |
| 16  | `frontend/app/tracer/page.module.css` | Add `.saveBtn` styles                      |
| 17  | `frontend/app/layout.tsx`             | Add SupabaseListener + export metadata     |
| 18  | `frontend/app/routers/__init__.py`    | Export get_current_user                    |
| 19  | `frontend/.env.local`                 | Add Supabase env vars                      |


---

## Detailed Implementation Instructions

### File 1 — `frontend/types/user.ts` (NEW)

Create this first. All other files depend on it.

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
  next_review_date: string;  // ISO "YYYY-MM-DD" — string, NOT Date
  interval_days: number;
  easiness_factor: number;
  repetitions: number;
  due: boolean;
  trace?: SavedTrace;
}

export interface DashboardData {
  traces: SavedTrace[];
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
```

---

### File 2 — `frontend/app/auth/auth.module.css` (NEW)

Shared styles for login and signup pages.

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
.title { font-size: 20px; font-weight: 700; color: #e6edf3; text-align: center; margin: 0 0 8px; }
.subtitle { font-size: 13px; color: #8b949e; text-align: center; margin: 0 0 28px; }
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
.input:focus { border-color: #388bfd; box-shadow: 0 0 0 3px rgba(56,139,253,0.15); }

.error {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px;
  background: rgba(248,81,73,0.1); border: 1px solid rgba(248,81,73,0.3);
  border-radius: 6px; color: #f85149; font-size: 13px;
}

.success {
  display: flex; flex-direction: column; gap: 12px;
  padding: 14px 16px;
  background: rgba(35,134,54,0.1); border: 1px solid rgba(35,134,54,0.3);
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
.submitBtn:hover:not(:disabled) { background: linear-gradient(135deg, #388bfd, #58a6ff); transform: translateY(-1px); }
.submitBtn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

.link { color: #58a6ff; text-decoration: none; font-weight: 500; }
.link:hover { text-decoration: underline; }
.footer { margin-top: 20px; text-align: center; font-size: 13px; color: #8b949e; }
```

---

### File 3 — `frontend/app/auth/login/page.tsx` (NEW)

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
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com" required autoComplete="email" className={styles.input} />
          </div>
          <div className={styles.field}>
            <label htmlFor="password" className={styles.label}>Password</label>
            <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password" required autoComplete="current-password" className={styles.input} />
          </div>
          {error && <div className={styles.error}><span>⚠</span> {error}</div>}
          <button type="submit" disabled={loading || !email || !password} className={styles.submitBtn}>
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

### File 4 — `frontend/app/auth/signup/page.tsx` (NEW)

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
        setSuccessMessage("Account created! Check your email to confirm your account before signing in.");
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
              <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com" required autoComplete="email" className={styles.input} />
            </div>
            <div className={styles.field}>
              <label htmlFor="password" className={styles.label}>Password</label>
              <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters" required minLength={6} autoComplete="new-password" className={styles.input} />
            </div>
            <div className={styles.field}>
              <label htmlFor="confirmPassword" className={styles.label}>Confirm password</label>
              <input id="confirmPassword" type="password" value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Repeat your password" required autoComplete="new-password" className={styles.input} />
            </div>
            {error && <div className={styles.error}><span>⚠</span> {error}</div>}
            <button type="submit" disabled={loading || !email || !password || !confirmPassword} className={styles.submitBtn}>
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

### File 5 — `frontend/app/auth/callback/route.ts` (NEW)

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

### File 6 — `frontend/app/dashboard/page.module.css` (NEW)

```css
/* frontend/app/dashboard/page.module.css */
.page { min-height: 100vh; background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

.loading {
  display: flex; align-items: center; justify-content: center; min-height: 100vh;
  gap: 12px; color: #8b949e; font-size: 14px;
}
.spinner { animation: spin 1s linear infinite; color: #58a6ff; font-size: 20px; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.topBar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: 56px; border-bottom: 1px solid #21262d; background: #161b22;
}
.brandLink { display: flex; align-items: center; gap: 8px; text-decoration: none; }
.logo { font-size: 20px; color: #58a6ff; }
.brandName { font-size: 16px; font-weight: 700; color: #e6edf3; }
.actions { display: flex; align-items: center; gap: 16px; }

.newTraceBtn {
  padding: 8px 16px; background: linear-gradient(135deg, #1f6feb, #388bfd);
  border-radius: 6px; color: white; font-size: 13px; font-weight: 600;
  text-decoration: none; transition: all 0.15s;
}
.newTraceBtn:hover { background: linear-gradient(135deg, #388bfd, #58a6ff); transform: translateY(-1px); }
.userMenu { display: flex; align-items: center; gap: 12px; }
.userEmail { font-size: 13px; color: #8b949e; }

.signOutBtn {
  padding: 6px 12px; background: transparent; border: 1px solid #30363d;
  border-radius: 6px; color: #8b949e; font-size: 12px; font-family: inherit;
  cursor: pointer; transition: all 0.15s;
}
.signOutBtn:hover { background: #21262d; color: #e6edf3; }

.main {
  max-width: 1100px; margin: 0 auto; padding: 32px 24px;
  display: flex; flex-direction: column; gap: 40px;
}

.errorBanner {
  display: flex; align-items: center; gap: 8px; padding: 12px 16px;
  background: rgba(248,81,73,0.1); border: 1px solid rgba(248,81,73,0.3);
  border-radius: 8px; color: #f85149; font-size: 13px;
}

.sectionHeader {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;
}
.sectionTitle { font-size: 18px; font-weight: 700; color: #e6edf3; margin: 0; }
.count { font-size: 13px; color: #8b949e; }
.streakBadge { font-size: 13px; font-weight: 600; color: #f59e0b; }

.emptyState {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; padding: 60px 20px; background: #161b22; border: 1px solid #21262d;
  border-radius: 12px; text-align: center;
}
.emptyState p { margin: 0; color: #8b949e; font-size: 14px; }
.emptyHint { font-size: 13px !important; color: #484f58 !important; }

.traceGrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }

.traceCard {
  background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 16px;
  display: flex; flex-direction: column; gap: 10px; transition: border-color 0.15s;
}
.traceCard:hover { border-color: #30363d; }

.codePreview { background: #0d1117; border-radius: 6px; padding: 10px 12px; margin: 0; overflow: hidden; }
.codePreview code {
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace; font-size: 11px;
  color: #8b949e; white-space: pre; display: block; max-height: 80px; overflow: hidden;
}

.traceTags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag {
  padding: 2px 8px; background: rgba(88,166,255,0.1); border: 1px solid rgba(88,166,255,0.2);
  border-radius: 12px; font-size: 11px; color: #58a6ff;
}
.traceFooter { display: flex; align-items: center; justify-content: space-between; }
.traceDate { font-size: 12px; color: #484f58; }
.traceActions { display: flex; gap: 6px; }
.actionBtn {
  padding: 4px 10px; background: #21262d; border-radius: 4px; color: #e6edf3;
  font-size: 12px; font-weight: 500; text-decoration: none; transition: background 0.15s;
}
.actionBtn:hover { background: #30363d; }
.actionBtnSecondary {
  padding: 4px 10px; border-radius: 4px; color: #8b949e; font-size: 12px;
  text-decoration: none; transition: color 0.15s;
}
.actionBtnSecondary:hover { color: #e6edf3; }

.cardGrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }

.reviewCard {
  background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 16px;
  display: flex; flex-direction: column; gap: 8px; transition: border-color 0.15s;
}
.reviewCard:hover { border-color: #30363d; }
.reviewCardHeader { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.conceptTag { font-size: 13px; font-weight: 600; color: #e6edf3; }
.dueLabel { font-size: 12px; color: #f59e0b; font-weight: 500; }
.reviewCardMeta { font-size: 12px; color: #484f58; }
.reviewBtn {
  margin-top: 4px; padding: 7px 14px; background: linear-gradient(135deg, #1f6feb, #388bfd);
  border-radius: 6px; color: white; font-size: 13px; font-weight: 600; text-decoration: none;
  text-align: center; transition: all 0.15s;
}
.reviewBtn:hover { background: linear-gradient(135deg, #388bfd, #58a6ff); transform: translateY(-1px); }
```

---

### File 7 — `frontend/app/dashboard/page.tsx` (NEW)

```typescript
// frontend/app/dashboard/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getSupabase } from "@/lib/supabase";
import { fetchDashboard, fetchDueReviews } from "@/lib/api";
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
        const [dash, reviews] = await Promise.all([fetchDashboard(), fetchDueReviews()]);
        setTraces(dash.traces);
        setStreak(reviews.streak);
        setDueCards(reviews.cards);
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
        {error && <div className={styles.errorBanner}><span>⚠</span> {error}</div>}

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
              <p className={styles.emptyHint}>Paste a function and click "Save to Review Queue" to get started.</p>
            </div>
          ) : (
            <div className={styles.traceGrid}>
              {traces.map((trace) => (
                <div key={trace.id} className={styles.traceCard}>
                  <pre className={styles.codePreview}><code>{truncateCode(trace.code)}</code></pre>
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
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
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

### File 8 — `frontend/app/review/[card_id]/review.module.css` (NEW)

```css
/* frontend/app/review/[card_id]/review.module.css */
.page {
  min-height: 100vh; background: #0d1117; color: #e6edf3;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  display: flex; flex-direction: column;
}
.loading, .errorState {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 100vh; gap: 12px; color: #8b949e; font-size: 14px;
}
.spinner { animation: spin 1s linear infinite; color: #58a6ff; font-size: 20px; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.topBar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; height: 56px; border-bottom: 1px solid #21262d; background: #161b22;
}
.backLink { font-size: 13px; color: #8b949e; text-decoration: none; transition: color 0.15s; }
.backLink:hover { color: #e6edf3; }
.cardInfo { display: flex; align-items: center; gap: 12px; }
.conceptTag {
  padding: 4px 12px; background: rgba(88,166,255,0.1); border: 1px solid rgba(88,166,255,0.2);
  border-radius: 16px; font-size: 13px; font-weight: 600; color: #58a6ff;
}
.main { flex: 1; display: flex; flex-direction: column; }
.editorSection { flex: 1; overflow: hidden; border-bottom: 1px solid #21262d; }
.editorLoading, .noCode {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; gap: 8px; color: #484f58; font-size: 13px;
}
.hint { color: #30363d; }
.progressBar { height: 3px; background: #21262d; flex-shrink: 0; }
.progressFill { height: 100%; background: linear-gradient(90deg, #1f6feb, #388bfd); transition: width 0.1s linear; }

.ratingPanel {
  padding: 32px 24px; background: #161b22; border-top: 1px solid #21262d;
  display: flex; flex-direction: column; align-items: center; gap: 20px;
  animation: slideUp 0.2s ease-out;
}
@keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
.ratingTitle { font-size: 16px; font-weight: 600; color: #e6edf3; margin: 0; }
.ratingButtons { display: flex; gap: 12px; }
.ratingBtn {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 14px 28px; border-radius: 10px; border: 1px solid; font-family: inherit; cursor: pointer; transition: all 0.15s;
}
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

.submittedPanel {
  padding: 48px 24px; background: #161b22; border-top: 1px solid #21262d;
  display: flex; flex-direction: column; align-items: center; gap: 16px; animation: slideUp 0.2s ease-out;
}
.submittedIcon {
  width: 56px; height: 56px; border-radius: 50%; background: rgba(35,134,54,0.15);
  border: 2px solid #3fb950; display: flex; align-items: center; justify-content: center;
  font-size: 24px; color: #3fb950;
}
.submittedTitle { font-size: 20px; font-weight: 700; color: #e6edf3; margin: 0; }
.submittedInfo { font-size: 14px; color: #8b949e; margin: 0; }
.dashboardBtn {
  margin-top: 8px; padding: 10px 20px; background: #21262d; border: 1px solid #30363d;
  border-radius: 6px; color: #e6edf3; font-size: 14px; font-family: inherit; cursor: pointer; transition: all 0.15s;
}
.dashboardBtn:hover { background: #30363d; }
.backBtn { color: #58a6ff; text-decoration: none; font-size: 13px; }
.backBtn:hover { text-decoration: underline; }
```

---

### File 9 — `frontend/app/review/[card_id]/page.tsx` (NEW)

```typescript
// frontend/app/review/[card_id]/page.tsx
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { getSupabase } from "@/lib/supabase";
import { fetchDueReviews, submitReviewRating } from "@/lib/api";
import { formatNextReview } from "@/lib/sm2";
import type { ReviewCard, SavedTrace } from "@/types/user";
import type { TraceStep } from "@/types/trace";
import styles from "./review.module.css";

const CodeEditor = dynamic(
  () => import("@/components/editor/CodeEditor").then((m) => m.CodeEditor),
  { ssr: false, loading: () => <div className={styles.editorLoading}>Loading code...</div> }
);

type ReviewState = "loading" | "playing" | "rating" | "submitted" | "error";

const INTERVAL_MS = 750;

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const cardId = params.card_id as string;

  const [card, setCard] = useState<ReviewCard | null>(null);
  const [trace, setTrace] = useState<SavedTrace | null>(null);
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

  // Load card + trace data
  useEffect(() => {
    async function load() {
      const { data: { session } } = getSupabase().auth.getSession();
      if (!session) { router.replace("/auth/login"); return; }
      try {
        const data = await fetchDueReviews();
        const found = data.cards.find((c) => c.id === cardId);
        if (!found) { setError("Card not found or already reviewed."); setReviewState("error"); return; }
        setCard(found);
        if (found.trace) {
          setTrace(found.trace);
          setSteps(found.trace.steps ?? []);
        }
        setReviewState("playing");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load card");
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
            setReviewState("rating");
            lastTimestampRef.current = null;
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

  // Trigger auto-play when state is ready
  useEffect(() => {
    if (reviewState === "playing") {
      const timer = setTimeout(() => {
        if (steps.length > 0) { startAnimation(steps); }
        else { setReviewState("rating"); }
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [reviewState]);

  // Cleanup
  useEffect(() => {
    return () => {
      playingRef.current = false;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const handleRating = useCallback(async (r: "again" | "hard" | "good" | "easy") => {
    setRating(r);
    try {
      const result = await submitReviewRating(cardId, r);
      setNextReview(result.next_review_date);
      setNextInterval(result.new_interval_days);
      setReviewState("submitted");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit review");
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
          {trace ? (
            <CodeEditor
              code={trace.code}
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

        {reviewState === "rating" && (
          <div className={styles.ratingPanel}>
            <h2 className={styles.ratingTitle}>How well did you understand this?</h2>
            <div className={styles.ratingButtons}>
              {(["again", "hard", "good", "easy"] as const).map((r) => (
                <button key={r} onClick={() => handleRating(r)} disabled={rating !== null}
                  className={`${styles.ratingBtn} ${styles[`ratingBtn_${r}`]}`}>
                  <span className={styles.ratingLabel}>{r === "again" ? "Again" : r === "hard" ? "Hard" : r === "good" ? "Good" : "Easy"}</span>
                  <span className={styles.ratingHint}>{r === "again" ? "Forgot it" : r === "hard" ? "Struggled" : r === "good" ? "Got it" : "Too easy"}</span>
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
            <button onClick={() => router.push("/dashboard")} className={styles.dashboardBtn}>← Back to Dashboard</button>
          </div>
        )}
      </main>
    </div>
  );
}
```

---

### File 10 — `frontend/app/trace/[share_token]/share.module.css` (NEW)

```css
/* frontend/app/trace/[share_token]/share.module.css */
.page {
  display: flex; flex-direction: column; height: 100vh;
  background: #0d1117; color: #e6edf3;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.notFound {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 100vh; gap: 12px; text-align: center; padding: 20px;
}
.notFound h1 { margin: 0; font-size: 24px; color: #e6edf3; }
.notFound p { margin: 0; color: #8b949e; font-size: 14px; }
.homeLink { margin-top: 8px; color: #58a6ff; text-decoration: none; font-size: 14px; }

.topBar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; height: 56px; border-bottom: 1px solid #21262d;
  background: #161b22; flex-shrink: 0;
}
.brand { display: flex; align-items: center; gap: 8px; text-decoration: none; }
.logo { font-size: 20px; color: #58a6ff; }
.brandName { font-size: 16px; font-weight: 700; color: #e6edf3; }
.actions { display: flex; gap: 8px; }

.saveBtn {
  padding: 8px 16px; background: #21262d; border: 1px solid #30363d; border-radius: 6px;
  color: #8b949e; font-size: 13px; font-weight: 500; font-family: inherit;
  cursor: pointer; transition: all 0.15s;
}
.saveBtn:hover:not(:disabled) { background: #30363d; color: #e6edf3; }
.saveBtn:disabled { opacity: 0.5; cursor: not-allowed; }

.traceBtn {
  padding: 8px 20px; border: none; border-radius: 6px;
  background: linear-gradient(135deg, #1f6feb, #388bfd); color: white;
  font-size: 14px; font-weight: 600; font-family: inherit; cursor: pointer; transition: all 0.15s;
}
.traceBtn:hover:not(:disabled) { background: linear-gradient(135deg, #388bfd, #58a6ff); transform: translateY(-1px); }
.traceBtn:disabled { opacity: 0.5; cursor: not-allowed; }

.errorBanner {
  display: flex; align-items: center; gap: 10px; padding: 10px 20px;
  background: rgba(248,81,73,0.1); border-bottom: 1px solid rgba(248,81,73,0.2);
  color: #f85149; font-size: 13px; flex-shrink: 0;
}
.dismissBtn { margin-left: auto; background: transparent; border: none; color: inherit; cursor: pointer; font-size: 12px; padding: 2px 6px; }

.main { display: flex; flex: 1; overflow: hidden; }
.editorPanel { flex: 6; overflow: hidden; border-right: 1px solid #21262d; }
.editorLoading {
  display: flex; align-items: center; justify-content: center; height: 100%;
  background: #0d1117; color: #484f58; font-size: 13px;
}
.rightPanel { flex: 4; overflow: hidden; }
.footer { border-top: 1px solid #21262d; flex-shrink: 0; }
```

---

### File 11 — `frontend/app/trace/[share_token]/page.tsx` (NEW)

```typescript
// frontend/app/trace/[share_token]/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { fetchSharedTrace, saveTrace } from "@/lib/api";
import { getSupabase } from "@/lib/supabase";
import type { SavedTrace } from "@/types/user";
import type { TraceStep, TraceResult } from "@/types/trace";
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

  const [trace, setTrace] = useState<SavedTrace | null>(null);
  const [code, setCode] = useState("");
  const [traceResult, setTraceResult] = useState<TraceResult | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchSharedTrace(shareToken) as SavedTrace & { steps?: TraceStep[] };
        setTrace(data);
        setCode(data.code);
        if (data.steps?.length) {
          setTraceResult({ trace_id: data.id, steps: data.steps, total_steps: data.steps.length, duration_ms: 0 });
          setCurrentStep(0);
        }
      } catch (err) {
        if (err instanceof Error && err.message === "TRACE_NOT_FOUND") { setNotFound(true); }
        else { setError(err instanceof Error ? err.message : "Failed to load trace"); }
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
    try {
      const result = await saveTrace({ code, steps: traceResult.steps, concept_tags: trace?.concept_tags ?? [] });
      router.push(`/trace/${result.share_token}`);
    } catch (err) {
      if (err instanceof Error && err.message === "AUTH_REQUIRED") { router.push("/auth/login"); return; }
      setError(err instanceof Error ? err.message : "Failed to save trace");
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
          <button onClick={handleSave} disabled={!traceResult} className={styles.saveBtn}>💾 Save</button>
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

### File 12 — `backend/app/routers/auth.py` (NEW)

```python
# backend/app/routers/auth.py
"""
Supabase JWT verification — validates Bearer token and returns the user record.
Used as a dependency by other routers: Depends(get_current_user)
"""
from fastapi import HTTPException, Header
from typing import Optional
import httpx

async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Verify the Authorization: Bearer <token> header against Supabase.
    Returns the decoded user dict from Supabase /auth/v1/user.
    Raises HTTPException 401 if token is missing, invalid, or expired.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Use: Authorization: Bearer <token>",
        )

    token = authorization[7:]

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

---

### File 13 — `frontend/app/supabase-provider.tsx` (NEW)

This client component wraps the app and listens for auth state changes. It ensures the UI stays in sync when the session changes (e.g., after login, logout, or token refresh).

```typescript
// frontend/app/supabase-provider.tsx
"use client";

import { useEffect } from "react";
import { getSupabase } from "@/lib/supabase";

export function SupabaseListener() {
  useEffect(() => {
    const supabase = getSupabase();
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, _session) => {
      // Auth state changed — Next.js router will handle any navigation needed
    });
    return () => subscription.unsubscribe();
  }, []);

  return null;
}
```

---

## Modifications to Existing Files

### Modify `frontend/lib/api.ts` — ADD these functions (keep existing ones)

Add after the existing `runTrace` and `explainLine` functions:

```typescript
// ── Auth helper ──────────────────────────────────────────────────────
async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = await getAuthToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(url, { ...options, headers });
}

// ── Dashboard ───────────────────────────────────────────────────────
export async function fetchDashboard(): Promise<DashboardData> {
  const res = await authFetch(`${API_BASE}/api/traces`);
  if (res.status === 401) throw new Error("AUTH_REQUIRED");
  if (!res.ok) throw new Error(`Failed to load dashboard: ${res.status}`);
  return res.json();
}

export async function saveTrace(params: {
  code: string;
  language?: string;
  steps: import("@/types/trace").TraceStep[];
  concept_tags?: string[];
}): Promise<SaveTraceResponse> {
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
export async function fetchDueReviews(): Promise<DueReviewsData> {
  const res = await authFetch(`${API_BASE}/api/review/due`);
  if (res.status === 401) throw new Error("AUTH_REQUIRED");
  if (!res.ok) throw new Error(`Failed to load reviews: ${res.status}`);
  return res.json();
}

export async function submitReviewRating(
  cardId: string,
  rating: "again" | "hard" | "good" | "easy"
): Promise<SubmitReviewResponse> {
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
export async function fetchSharedTrace(shareToken: string): Promise<SavedTrace & { steps?: import("@/types/trace").TraceStep[] }> {
  const res = await fetch(`${API_BASE}/api/traces/shared/${shareToken}`);
  if (res.status === 404) throw new Error("TRACE_NOT_FOUND");
  if (!res.ok) throw new Error(`Failed to load trace: ${res.status}`);
  return res.json();
}

export async function shareTrace(traceId: string): Promise<{ share_token: string; share_url: string }> {
  const res = await authFetch(`${API_BASE}/api/traces/${traceId}/share`, { method: "POST" });
  if (res.status === 401) throw new Error("AUTH_REQUIRED");
  if (!res.ok) throw new Error(`Failed to share trace: ${res.status}`);
  return res.json();
}
```

### Modify `frontend/app/layout.tsx`

Replace the file contents with:

```tsx
// frontend/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import { SupabaseListener } from "./supabase-provider";

export const metadata: Metadata = {
  title: "CodeScope",
  description: "Visualize Python code execution step by step",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
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

### Modify `frontend/app/tracer/page.tsx`

Add these imports at the top:

```tsx
import { getSupabase } from "@/lib/supabase";
import { saveTrace } from "@/lib/api";
```

Add this helper function (before the component):

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

Add `router` to the component and add this callback:

```tsx
const router = useRouter();

// Add handleSaveTrace:
const handleSaveTrace = useCallback(async () => {
  if (!traceResult?.steps?.length) return;
  const { data: { session } } = getSupabase().auth.getSession();
  if (!session) { router.push("/auth/login"); return; }
  try {
    await saveTrace({ code, steps: traceResult.steps, concept_tags: extractConceptTags(code) });
  } catch (err) {
    if (err instanceof Error && err.message.includes("UPGRADE_REQUIRED")) {
      setError("Free plan limit reached. Upgrade to Pro to save more traces.");
    } else {
      setError(err instanceof Error ? err.message : "Failed to save");
    }
  }
}, [code, traceResult, router]);
```

Add the Save button to the `actions` div (before the Trace button):

```tsx
<button
  className={styles.saveBtn}
  onClick={handleSaveTrace}
  disabled={!traceResult}
  title={!traceResult ? "Run the trace first" : "Save this trace"}
>
  💾 Save
</button>
```

### Modify `frontend/app/tracer/page.module.css`

Add these styles:

```css
.saveBtn {
  padding: 8px 16px; background: #21262d; border: 1px solid #30363d;
  border-radius: 6px; color: #8b949e; font-size: 13px; font-weight: 500;
  cursor: pointer; transition: all 0.15s;
}
.saveBtn:hover:not(:disabled) { background: #30363d; color: #e6edf3; }
.saveBtn:disabled { opacity: 0.4; cursor: not-allowed; }
```

### Modify `backend/app/routers/__init__.py`

Add this line to export `get_current_user` so other routers can import it:

```python
# backend/app/routers/__init__.py
from .auth import get_current_user
```

---

## Backend Changes (Python)

### Modify `backend/app/main.py`

Add routers if not already present. The review router should have the `/api/review` prefix:

```python
from app.routers.traces import router as traces_router
from app.routers.llm import router as llm_router
from app.routers.review import router as review_router
from app.routers.profiles import router as profiles_router

app.include_router(traces_router)           # prefix=""  — /api/traces/run
app.include_router(llm_router)             # prefix=""  — /api/llm/explain/stream
app.include_router(review_router, prefix="/api/review")  # /api/review/due, /api/review/{id}
app.include_router(profiles_router)
```

### Modify `backend/app/routers/traces.py`

Add these endpoints to the existing router:

```python
@router.get("/api/traces")
async def list_traces(authorization: str = Header(None), limit: int = 20, offset: int = 0):
    """List user's saved traces. Auth required."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    from app.routers.auth import get_current_user
    user = await get_current_user(authorization)
    user_id = user.get("id", "")

    from app.config import Settings
    settings = Settings()
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"user_id": f"eq.{user_id}", "select": "*", "limit": str(limit), "offset": str(offset), "order": "created_at.desc"},
            headers={"Authorization": f"Bearer {authorization[7:]}", "apikey": settings.supabase_service_key},
        )
    traces = resp.json() if resp.status_code == 200 else []
    return {"traces": traces, "total_traces": len(traces)}


@router.get("/api/traces/shared/{share_token}")
async def get_shared_trace(share_token: str):
    """Get a trace by its share token. Public endpoint."""
    from app.config import Settings
    settings = Settings()
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"share_token": f"eq.{share_token}", "is_public": "eq.true", "select": "*"},
            headers={"apikey": settings.supabase_service_key},
        )
    traces = resp.json() if resp.status_code == 200 else []
    if not traces:
        raise HTTPException(status_code=404, detail="Trace not found")
    return traces[0]


@router.post("/api/traces/{trace_id}/share")
async def share_trace(trace_id: str, authorization: str = Header(None)):
    """Generate or update a share link for a trace."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")
    # TODO: Verify ownership, generate/update share_token, set is_public=true
    import secrets
    share_token = secrets.token_hex(16)
    return {"share_token": share_token, "share_url": f"/trace/{share_token}"}
```

### Modify `backend/app/routers/review.py`

Replace the `TODO` stubs with real Supabase calls. The review router already has the endpoints — you need to wire up the Supabase client inside each handler:

```python
# Replace the get_due_reviews and submit_review bodies:

# At top of file, add:
import httpx
from app.config import Settings
from app.routers.auth import get_current_user

# In get_due_reviews():
user = await get_current_user(authorization)
user_id = user.get("id", "")
settings = Settings()
today = date.today().isoformat()

async with httpx.AsyncClient(timeout=10.0) as client:
    resp = await client.get(
        f"{settings.supabase_url}/rest/v1/review_cards",
        params={
            "user_id": f"eq.{user_id}",
            "next_review_date": f"lte.{today}",
            "select": "*",
        },
        headers={
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
        },
    )
cards = resp.json() if resp.status_code == 200 else []

# Mark cards as due and compute streak
for card in cards:
    card["due"] = True

# Calculate streak from review history (simplified — count consecutive days)
streak = len(cards)  # TODO: compute real streak from review_logs table
return DueReviewsResponse(cards=cards[:20], streak=streak, total_due=len(cards))

# In submit_review():
user = await get_current_user(authorization)
user_id = user.get("id", "")
quality = RATING_MAP[req.rating]

# Fetch current card state from Supabase
settings = Settings()
async with httpx.AsyncClient(timeout=10.0) as client:
    resp = await client.get(
        f"{settings.supabase_url}/rest/v1/review_cards",
        params={"id": f"eq.{card_id}", "user_id": f"eq.{user_id}", "select": "*"},
        headers={"Authorization": f"Bearer {authorization[7:]}", "apikey": settings.supabase_service_key},
    )
cards = resp.json() if resp.status_code == 200 else []
if not cards:
    raise HTTPException(status_code=404, detail="Card not found")
card = cards[0]

new_ef, new_interval, new_reps, next_date = sm2_calculate(
    quality, card["easiness_factor"], card["interval_days"], card["repetitions"]
)

# Update card in Supabase
await client.patch(
    f"{settings.supabase_url}/rest/v1/review_cards",
    params={"id": f"eq.{card_id}"},
    headers={"Authorization": f"Bearer {authorization[7:]}", "apikey": settings.supabase_service_key, "Prefer": "return=minimal"},
    json={
        "easiness_factor": round(new_ef, 2),
        "interval_days": new_interval,
        "repetitions": new_reps,
        "next_review_date": next_date.isoformat(),
        "last_reviewed_at": "now()",
    },
)

return {"card_id": card_id, "new_interval_days": new_interval, "new_ef": round(new_ef, 2), "new_repetitions": new_reps, "next_review_date": next_date.isoformat()}
```

---

## Environment Variables

Add to `frontend/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
```

Add to `backend/.env` (if not already present):

```
SUPABASE_URL=http://localhost:54321
SUPABASE_SERVICE_KEY=postgres
```

---

## Integration Verification Checklist

Run through all of these manually. If any fail, the implementation is incomplete.

### Auth

- `/auth/login` — form renders, submit with wrong credentials → error message
- `/auth/login` — valid credentials → redirects to `/dashboard`
- `/auth/signup` — creates account → shows "check email" confirmation message
- `/auth/signup` — already-used email → shows friendly error
- `/auth/callback?code=...` → exchanges code → redirects to `/dashboard`
- Unauthenticated `/dashboard` → redirects to `/auth/login`
- Sign out → redirects to `/auth/login`

### Dashboard

- Shows traces grid (or empty state if none)
- Shows review queue (or empty state if none)
- "+ New Trace" → navigates to `/`
- "Open" on a trace card → opens `/trace/{share_token}`
- "Review Now" on a due card → opens `/review/{card_id}`
- Streak badge shows correct number

### Review Page

- Auto-plays animation on load (750ms/step)
- Rating buttons appear after animation completes
- Clicking a rating → calls API → shows "Review complete!"
- "← Back to Dashboard" works
- **CRITICAL:** `formatNextReview(new Date(next_review))` — note the `new Date()` wrapper

### Shared Trace Page

- `/trace/{valid_token}` → loads code
- `/trace/{invalid_token}` → shows "Trace not found"
- Edit code + click Trace → re-runs tracer
- Save button → prompts login if not authenticated

### Tracer Page (modified)

- Save button in top bar
- Save disabled when no trace result
- Clicking Save while logged out → redirects to `/auth/login`
- Clicking Save while logged in → saves (no navigation)

### Backend

- `GET /api/traces` returns user's traces (requires auth)
- `GET /api/traces/shared/{token}` returns public trace (no auth)
- `GET /api/review/due` returns due cards (requires auth)
- `POST /api/review/{id}` updates SM-2 params (requires auth)

---

## The 6 Rules That Prevent 90% of Bugs

1. `**next_review_date` is always a string.** Wrap with `new Date()` before calling `formatNextReview()`.
2. `**useRouter` is called at the top of every component.** Never inside a `useEffect` or conditionally.
3. `**requestAnimationFrame` cleanup.** Always cancel with `cancelAnimationFrame` in the cleanup function of `useEffect`.
4. `**"use client"` on every page file.** Every page in `app/auth/`, `app/dashboard/`, `app/review/`, `app/trace/` is a client component.
5. `**authFetch` attaches the token.** Never call auth-protected endpoints with plain `fetch` — use `authFetch` instead.
6. **Keep existing `api.ts` functions.** Add new functions; do not delete or replace the existing `runTrace` and `explainLine`.

