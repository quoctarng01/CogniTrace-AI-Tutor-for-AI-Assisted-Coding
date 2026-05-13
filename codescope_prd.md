# CodeScope PRD

**Metadata:**

- **Version:** 2.0
- **Date:** 2026-04-30
- **Author:** [Author]
- **Status:** Draft — for supervisor review
- **Based on:** `research_report.md`, `codescope_analysis.md`, `SPEC.md`, `ARCHITECTURE.md`
- **Changes from 1.1:** Removed formal research study (study mode, telemetry pipeline, evaluation pipeline, TelemetryEvent/TelemetrySession tables). CodeScope is a working product demo, not a research instrument. Freemium gate updated accordingly.

---

## 1. Overview

### Product Name

**CodeScope** — Real-time execution tracer for AI-generated Python code

### One-Line Description

CodeScope lets developers paste AI-generated Python code and watch it execute step-by-step with animated data-flow visualization — seeing exactly what each line does, which variables change, and which branches fire — before debugging blindly.

### Target User

**Priya, 23**, a final-year CS student who has been using GitHub Copilot to complete her final project. She has 60–80% of her code AI-generated. She can run the code, but when something breaks, she doesn't know where to look because she didn't write most of it. She can't debug it because she doesn't understand it. She can't ask for help because she can't explain what she built. Her fear: shipping broken code because she couldn't understand what she deployed.

**Secondary user:** **Marcus, 28**, a junior developer at a 15-person startup. He uses Cursor every day. His team lead just asked him to explain a feature he shipped last week — he couldn't. His fear: being exposed as not actually knowing how to code.

### Core Value Proposition

CodeScope is the only tool that closes the "AI code comprehension gap" — the gap between what developers can generate with AI and what they can understand about it. The visualization shows the gap, the "why" panel explains it, and the spaced repetition system locks the understanding in.

### The "Aha!" Moment

The moment Priya pastes a nested list comprehension, watches it animate through the comprehension step by step, and sees the orange pulse on the variable that just changed — she suddenly understands exactly why that comprehension works. She didn't get that from reading the code. She got it from watching it run.

### Primary Success Metric

**Trace completion rate: ≥ 80%** — of users who start tracing a snippet, ≥ 80% reach the final step without abandoning. This means the tracer is engaging enough to hold attention and the execution is understandable. Tracked via a `trace_started` and `trace_completed` event pair in Supabase (logged without personally identifiable information; no research study).

---

## 2. Goals & Non-Goals

### Goals (stated as outcomes, not features)

**Goal 1:** Users paste AI-generated Python code and receive a valid, step-by-step execution trace within 5 seconds of clicking "Trace" (excluding first-time server startup).

**Goal 2:** Users can navigate a trace forward and backward at variable speeds (0.5×–5×), with variable state updating in real time, so they can observe exactly what happens on any given line.

**Goal 3:** Users who encounter a confusing line can click "Why is this here?" and receive an LLM-generated explanation grounded in the current execution context (variable state, call stack) within 3 seconds, streamed word-by-word.

**Goal 4:** Users can save any traced function to a spaced repetition review queue, with reviews scheduled by the SM-2 algorithm, so they retain understanding over time rather than forgetting it within a week.

### Non-Goals

**Non-Goal 1:** This product will NOT execute code with side effects (file I/O, network calls, subprocess execution). The execution sandbox (backend subprocess with resource limits) is intentionally restricted. Code that requires side effects is rejected before execution.

**Non-Goal 2:** This product will NOT generate code for users. It is a comprehension tool, not a generation tool. It will never auto-complete or suggest code.

**Non-Goal 3:** This product will NOT support multi-language execution in V1. Only Python is supported. JavaScript, TypeScript, Java, and other languages are explicitly out of scope.

**Non-Goal 4:** This product will NOT be mobile-responsive in V1. It is a desktop tool optimized for 1280×720 and above. Mobile support is explicitly deferred.

---

## 3. User Stories

```
US-01 | P0 | As Priya, I want to paste an AI-generated Python function and see it
      |     execute line by line with variable states updating in real time, so that
      |     I can understand what each line actually does when it runs.

US-02 | P0 | As Priya, I want to pause on any line and ask "Why is this here?" and
      |     receive an explanation grounded in the current execution context, so that
      |     I can understand intent rather than just syntax.

US-03 | P0 | As Priya, I want to save any traced function to my review queue, so that
      |     the spaced repetition system schedules future reviews and I retain
      |     understanding of the code patterns I struggled with.

US-04 | P0 | As Priya, I want to step backward through a trace to revisit a confusing
      |     line, so that I can check my understanding before moving on without
      |     restarting the entire trace.

US-05 | P1 | As Priya, I want to see which AI-generated patterns (nested
      |     comprehensions, defensive None checks, implicit assumptions) appear in
      |     my code, so that I understand which patterns are most associated with
      |     my confusion.

US-06 | P1 | As Marcus, I want to share a trace link with a colleague, so that we
      |     can discuss a specific AI-generated function without them needing to
      |     paste the code themselves.

US-07 | P2 | As Marcus, I want to track my streak of daily reviews, so that I have
      |     a concrete measure of my learning progress and a reason to return
      |     to the tool daily.

US-08 | P1 | As Priya, I want a warning before execution if my code contains side
      |     effects (file I/O, network calls), so that I know why execution was
      |     blocked and feel confident the sandbox is safe.
```

---

## 4. Functional Requirements

### FREEMIUM GATE (explicit — required by AI EdTech checklist)


| Feature                       | Free Tier                                            | Pro Tier ($15/month) |
| ----------------------------- | ---------------------------------------------------- | -------------------- |
| Traces per month              | 50 (soft limit; prompts upgrade; not server-blocked) | Unlimited            |
| Save to review queue          | No                                                   | Yes                  |
| Spaced repetition             | No                                                   | Yes                  |
| "Why is this here?" questions | 20/hour                                              | Unlimited            |
| Dashboard + progress tracking | No                                                   | Yes                  |
| Share trace links             | No                                                   | Yes                  |
| Team features                 | No                                                   | V2                   |


> **Cost risk:** Ollama Cloud is free. Redis-backed rate limiting (Redis required for distributed deployments) ensures rate limits work correctly across all Railway instances. Claude API costs are covered by the $5 Anthropic free tier during MVP. Implement sliding window rate limiting on free tier (20/hour). Pro tier has unlimited access.

---

### Module: CORE

```
REQ-CORE-01: Code Input & Validation
Priority: Must Have
Description: User can paste or type Python code into a Monaco editor with Python
             syntax highlighting. Code is validated before execution.
Acceptance criteria:
  - Empty code: "Trace" button is disabled
  - Code with detected side effects (import, open, requests, subprocess, eval, socket):
    → Execution blocked, warning modal shown with specific pattern detected
  - Valid code: "Trace" button is enabled
  - Syntax errors: Error shown inline in editor with line number
Linked user story: US-01

REQ-CORE-02: Step-by-Step Execution Trace
Priority: Must Have
Description: When "Trace" is clicked, Python code is executed and instrumented by
             a custom tracer built on Python's `sys.settrace()` hook. This operates
             at the CPython bytecode level — every instruction fires the tracer callback,
             capturing: bytecode offset, line number, local variable state, call stack
             depth, and branch decisions. Branch detection is IMPLEMENTED in v1:
             the tracer detects which branch of an if/elif/else fired, loop iteration
             counts for for/while loops, and boolean short-circuit decisions.
Branch Detection Implementation:
  - AST pre-pass: parses code AST to find all conditional nodes and their target lines
  - Bytecode inspection: maps POP_JUMP_IF_TRUE/FALSE to branch decisions
  - Loop tracking: FOR_ITER bytecode events are counted per line → iteration count
  - Output: branches_taken dict per step, e.g. {"type": "if", "taken": true, "line": 5}
⚠ SPIKE NEEDED in Week 1: Profile tracer overhead on 200-line functions.
             If tracer adds > 200ms latency, move to FastAPI `run_in_executor()` thread pool
             to keep the async event loop responsive without blocking concurrent requests.
Acceptance criteria:
  - Tracer implemented in `backend/tracer/` as a standalone, pip-installable library
  - Maximum 500 steps per trace (infinite loop protection)
  - Timeout: 5 seconds per execution; auto-kill if exceeded
  - Trace generation: ≤ 3 seconds for 200-line function (excluding network transit)
  - Tracer works with any standard library: numpy, pandas, datetime, etc.
  - branches_taken populated: if/elif/else branches, loop iterations, and/or short-circuit
Linked user story: US-01

REQ-CORE-03: Variable State Panel
Priority: Must Have
Description: Live display of all local variables during trace playback.
             Each variable shows: name, type badge (color-coded), current value.
             Variables that changed on the current step pulse orange.
Acceptance criteria:
  - Variables appear/disappear as they enter/leave scope
  - Type badges: int=blue, str=green, list=purple, dict=orange, func=gray
  - Changed variable: 200ms orange pulse animation on the step it changes
  - Empty state (before execution): "Run the trace to see variable states"
Linked user story: US-01, US-04

REQ-CORE-04: Animation Controls
Priority: Must Have
Description: Play, Pause, Step Forward, Step Back controls for trace navigation.
             Speed selector (0.5×, 1×, 2×, 5×). Keyboard shortcuts.
             Animation loop uses requestAnimationFrame (not setInterval) for precision.
Acceptance criteria:
  - Play: rAF-driven advance through all steps at selected speed
  - Pause: cancelAnimationFrame called — current step preserved
  - Step Forward: cancel rAF → advance exactly one step → stay paused
  - Step Backward: cancel rAF → retreat exactly one step (disabled at step 0) → stay paused
  - Speed 1×: 750ms per step
  - Tab visibility handling: pauses automatically when tab is backgrounded (document.hidden)
  - Keyboard shortcuts: Space (play/pause), Arrow Right (step forward), Arrow Left (step back),
    Home (reset to 0), End (jump to last step) — work when tracer is focused
Linked user story: US-04

REQ-CORE-05: Current Line Highlighting
Priority: Must Have
Description: The currently executing line is highlighted in the Monaco editor
             with a blue background (#1F6FEB) and left border.
Acceptance criteria:
  - Highlighted line updates on every step change
  - Clicking a line activates the "Why is this here?" button for that line
  - No highlight when trace is not running
Linked user story: US-01, US-02
```

---

### Module: AI

```
REQ-AI-01: "Why is this here?" Explanations
Priority: Must Have
Description: Clicking "Why is this here?" on any line sends the code context,
             current variable state, and line number to the LLM (Ollama Cloud).
             Returns a plain-English explanation grounded in the current state,
             streamed word-by-word via Server-Sent Events.
AI Prompt Strategy:
  System prompt: "You are a Python code educator. Explain why a specific line of
  code exists, given the current execution context. Current line: {lineContent}.
  Current variable state: {locals}. Explain in 2-3 sentences. Be precise. Do not
  explain what the code does generally — explain WHY this specific line is necessary
  given the current state. Include a code snippet if helpful."
Provider routing (llm_router.py):
  1. Ollama Cloud (https://ollama.com/api) — primary, free, zero setup
  2. Local Ollama (localhost:11434) — optional, for users with local inference
  3. Claude Sonnet 4 (ANTHROPIC_API_KEY) — fallback only
Acceptance criteria:
  - Response streamed word-by-word via SSE (≤ 3 seconds to first token)
  - Response cached by SHA-256 hash(code[:200] + line_number + line_content[:50]) —
    repeat clicks on the same line return instantly at zero API cost
  - Streaming indicator: blinking cursor while response streams
  - Error state: "Couldn't generate explanation. [Try Again]"
  - Response rendered as markdown with syntax-highlighted code snippets
  - Rate limit: 20 "why" questions/hour on free tier (enforced server-side)
Linked user story: US-02

REQ-AI-02: Explanation Quality Rating
Priority: Should Have (Month 2)
Description: After viewing a "why" explanation, user can rate it Helpful /
             Not Helpful. Rating is stored for future prompt improvement.
AI Prompt Strategy for future improvement:
  Track mean helpfulness rating by pattern category.
  If category mean < 3.0/5.0: revise prompt template for that pattern.
Acceptance criteria:
  - Rating widget: 5-point scale (1 = Not helpful at all, 5 = Very helpful)
  - Rating stored in explanations.human_rating (1–5) in Supabase
  - Used to inform future prompt refinement (not visible to other users)
Linked user story: US-02

The "cheating problem" — how CodeScope prevents bypassing the learning mechanism:
  CodeScope does NOT prevent users from copying the "why" explanation and moving on.
  This is an intentional design choice: coercive "prove you understood" gates create
  adversarial behavior. Instead, the spaced repetition review queue is the learning
  mechanism — understanding is tested at review time, not at trace time.
```

---

### Module: TRACKING

```
REQ-TRACK-01: Save to Review Queue
Priority: Must Have
Description: Any traced function can be saved to the user's review queue with
             auto-detected concept tags.
Acceptance criteria:
  - "Save to Review Queue" button appears after trace completes (Pro users only)
  - Concept tags shown before saving (auto-detected from code)
  - Saved traces appear in dashboard review queue
  - Free users: button shows "Upgrade to Pro" instead
Linked user story: US-03

REQ-TRACK-02: SM-2 Spaced Repetition Scheduler
Priority: Must Have
Description: Review cards are scheduled by the SuperMemo 2 algorithm.
             After each review, user rates recall (Again/Hard/Good/Easy).
             Interval updates per SM-2 formula.
Acceptance criteria:
  - First review: due immediately after save
  - After "Again": interval resets to 1 day
  - After "Hard": interval unchanged, EF decreases
  - After "Good": interval = 1 day (first), then 6 days, then × EF
  - After "Easy": interval = 4 days (first), then × 1.3 × EF
  - Easiness factor: minimum 1.3, updated after each review
  - Algorithm: SuperMemo 2 (SM-2). Easiness factor: minimum 1.3, updated after each review
Linked user story: US-03

REQ-TRACK-03: Review Interface
Priority: Should Have (Month 3)
Description: User reviews a saved trace by replaying it and rating recall.
Acceptance criteria:
  - Review queue sorted by due date (overdue at top)
  - Streak counter: consecutive days with ≥ 1 completed review
  - Empty state: "No reviews due. Trace some code to build your queue."
  - After replaying trace: recall rating (Again/Hard/Good/Easy) shown
  - After review: next due date shown; user returned to dashboard
Linked user story: US-03, US-07

REQ-TRACK-04: Concept Tagging
Priority: Could Have (Month 2)
Description: AI code patterns automatically detected and tagged when code is saved.
             Tags: COMPLEX_CONTROL_FLOW, OVER_ENGINEERING, API_USAGE,
             IMPLICIT_ASSUMPTIONS, DEEP_RECURSION.
Acceptance criteria:
  - 3+ pattern categories detectable in V1
  - Tags shown on saved trace cards
  - Tags filterable in review queue
Linked user story: US-05
```

---

### Module: AUTH

```
REQ-AUTH-01: Email/Password Sign-Up and Sign-In
Priority: Should Have (Month 3)
Description: Supabase Auth handles email/password sign-up, sign-in, sign-out.
             Dashboard and review queue require authentication.
             Tracer works without auth (anonymous, not saved).
Acceptance criteria:
  - Sign up: email + password → confirmation email → verified account
  - Sign in: email + password → authenticated session
  - Sign out: session cleared, returned to landing page
  - Protected routes redirect to /auth/login
Linked user story: US-03, US-07

REQ-AUTH-02: Share Trace Link
Priority: P1 (Month 3)
Description: Any saved trace can be shared via a unique URL. Anyone with the link
             can view the trace in read-only replay mode without an account.
Acceptance criteria:
  - "Share" button on saved traces generates a unique URL: /trace/{uuid}
  - Shared trace URL works without login (read-only)
  - Shared trace shows: code, visualization, and any saved annotations
  - Shared trace does NOT show: user identity, review data, personal dashboard
  - Creator can revoke sharing link at any time
Linked user story: US-06
```

---

## 5. User Flows

### Primary Flow — Trace and Understand

```
[TRIGGER] Priya pastes an AI-generated function into CodeScope
  Step 1: Code pasted into Monaco editor (Python syntax highlighted)
  Step 2: Side effect detection runs automatically
            → Blocked: warning modal shown with reason; execution stops
            → Allowed: "Trace" button becomes enabled
  Step 3: Priya clicks "Trace"
  Step 4: Code sent to backend; custom tracer instruments execution via sys.settrace()
  Step 5: Trace steps generated server-side; returned to frontend as JSON
  Step 6: Trace view activates — code editor on left, variable panel on right
  Step 7: Priya presses Space to play — trace advances step by step
            → Variables update in real time
            → Changed variables pulse orange
  Step 8: Priya clicks line 5 → "Why is this here?" button appears
  Step 9: Priya clicks "Why is this here?" (or hits free-tier limit → upgrade modal)
  Step 10: Explanation panel shows streaming response (word-by-word, ≤ 3s)
  Step 11: Priya rates explanation: Helpful / Not Helpful
  Step 12: Priya clicks "Save to Review Queue" (Pro only; free users → upgrade modal)
  Step 13: Concept tags shown: [COMPLEX_CONTROL_FLOW, NESTED_COMPREHENSION]
  Step 14: Saved confirmation → Priya redirected to dashboard

  [VALUE MOMENT]: Priya watches the nested comprehension execute step by step
                  and finally understands why it works. The visualization closed the gap.

  [DECISION POINT]:
    → Priya is on Pro → trace saved → review scheduled → added to dashboard
    → Priya is on Free → "Save" button shows "Upgrade to Pro"
```

### Freemium Paywall Flow

```
[TRIGGER] Priya has used 50 free traces this month
  Step 1: Priya clicks "Trace"
  Step 2: Soft limit modal appears:
            "You've used your 50 free traces this month.
             Upgrade to Pro for unlimited traces, review queues, and more."
            [Upgrade to Pro — $15/month]  [Maybe later]
  Step 3: Priya clicks "Upgrade to Pro"
  Step 4: Stripe checkout opens → credit card entry
  Step 5: Payment confirmed → Pro status activated → Priya continues tracing

Note: Free-tier trace count is tracked in localStorage as a soft limit —
it does not block execution, only prompts the upgrade modal. Pro tier enforces
no trace count limit. Saving traces (review queue) requires Pro regardless of
trace count.

[TRIGGER] Priya is on free tier and clicks "Save to Review Queue"
  Step 1: Upgrade modal appears:
            "Saving traces requires a Pro subscription."
            [Upgrade to Pro — $15/month]  [Maybe later]

[EDGE CASES]:
  - Payment fails → Priya remains on free tier; Stripe handles retry
  - Priya cancels subscription → reverts to free tier immediately; saved data retained
  - Priya hits "why" rate limit (20/hour on free) → modal: "Rate limit reached.
    Upgrade to Pro for unlimited 'why' questions." [Retry in X minutes]
```

---

## 6. UI/UX Requirements

### Tracer Page (Primary Product)

**Primary action:** Paste code → Trace → understand

**Key components:**

- Monaco code editor (left panel, 60% width)
- Variable state panel (right panel, 40% width)
- Animation controls (bottom bar)
- "Why is this here?" panel (slides in, SSE streaming)
- Action bar (top right): Save / Share

**Responsive:** Desktop-first. Minimum width: 1024px. Not optimized for mobile.

**Accessibility:** WCAG 2.1 AA. All controls keyboard-navigable. ARIA labels on all icon-only buttons. Focus states visible (blue outline). Color contrast ≥ 4.5:1. Screen reader compatible.

### Cold Start (empty states for every key screen)


| Screen                        | Empty State                                                                              |
| ----------------------------- | ---------------------------------------------------------------------------------------- |
| Tracer (before paste)         | Placeholder text in editor: "Paste your AI-generated Python code here"                   |
| Variable panel (before trace) | "Run the trace to see variable states"                                                   |
| Dashboard (no saved traces)   | "No traces saved yet. Paste a function and click 'Save to Review Queue' to get started." |
| Review queue (no due reviews) | "No reviews due. Trace some code to build your queue."                                   |
| Shared trace (invalid UUID)   | "This trace doesn't exist or has been removed."                                          |


---

## 7. Technical Requirements

### 7a. Tech Stack

```
Frontend:    Next.js 16 (App Router, TypeScript) — React Server Components
Backend:     FastAPI (Python) — handles trace execution, Ollama proxy, Claude fallback
Execution:   Custom tracer via Python's sys.settrace() — instruments CPython bytecode
             directly. Zero browser dependencies, zero WASM. Runs as isolated subprocess.
             ⚠ SPIKE NEEDED in Week 1: Profile tracer overhead on 200-line functions.
AI Layer:    Ollama Cloud (ollama.com/api) — free, zero setup, no GPU required (primary)
             Claude Sonnet 4 API — available as fallback when Ollama Cloud is unavailable
             ⚠ SPIKE NEEDED in Month 2: Benchmark explanation quality across Ollama models
Database:    Supabase (PostgreSQL + Auth + RLS) — free tier sufficient for MVP
Cache:       Redis (Upstash or Railway) — distributed rate limiting, session cache
Hosting:     Vercel (frontend, free) + Railway (backend, ~$5/month)
             Ollama Cloud handles inference for all users in production
```

### 7b. Data Models

```
Profile
  id: uuid (PK)
  user_id: uuid (FK → auth.users.id)
  experience_level: text ('student' | 'junior' | 'mid') — optional, self-reported
  ai_tools_usage: text ('none' | 'light' | 'moderate' | 'heavy') — optional
  python_years: int — optional
  ollama_endpoint: text (default 'https://ollama.com/api')
  stripe_customer_id: text — nullable
  plan: text ('free' | 'pro') — default 'free'
  created_at: timestamptz

Trace
  id: uuid (PK)
  user_id: uuid (FK → profiles.id)
  code: text
  language: text (default 'python')
  steps: jsonb
  concept_tags: text[]
  is_public: bool (default false)
  share_token: text (unique)
  created_at: timestamptz

ReviewCard
  id: uuid (PK)
  user_id: uuid (FK → profiles.id)
  trace_id: uuid (FK → traces.id)
  concept_tag: text
  easiness_factor: float (default 2.5)
  interval_days: int (default 1)
  repetitions: int (default 0)
  next_review_date: date
  last_reviewed_at: timestamptz
  created_at: timestamptz

Explanation
  id: uuid (PK)
  trace_id: uuid (FK → traces.id)
  line_number: int
  explanation_text: text
  cache_key: text (SHA-256 of code+line+content)
  model_used: text ('ollama' | 'claude')
  model_name: text
  cached: bool (default false)
  human_rating: int (nullable, 1–5)
  pattern_category: text
  created_at: timestamptz

Note: TelemetryEvent and TelemetrySession tables removed.
      No formal research study — no participant tracking, no session telemetry.
```

### 7c. API Endpoints (V1)

```
POST /api/traces/run
Auth: Optional (anonymous allowed; Pro unlocks save)
Description: Executes code via sys.settrace() subprocess. Returns step JSON.
             Side effects detected and blocked before execution.
Request:  { code: string }
Response: { trace_id: uuid, steps: TraceStep[], total_steps: int, duration_ms: float }
Errors:   422 (side effect detected), 500 (timeout or runtime error)

POST /api/traces
Auth: Required (Pro for unlimited, free max 50/month)
Request:  { code: string, concept_tags: string[], is_public: bool }
Response: { id: uuid, share_token: string, created_at: string }
Errors:   401 (not authenticated), 402 (free tier limit), 422 (validation)

GET /api/traces
Auth: Required
Response: { traces: Trace[] }

GET /trace/{share_token}
Auth: None (public, read-only)
Response: { trace: Trace } or 404

GET /api/llm/explain/stream
Auth: Pro (unlimited) OR anonymous (rate-limited: 20/hour)
Description: Streams explanation via SSE. Ollama Cloud primary; Claude fallback.
Query params: code, line_number, line_content, locals_json
Response: Server-Sent Events stream of tokens
Errors:   429 (rate limit), 500 (all providers failed)

POST /api/review/due
Auth: Pro required
Response: { cards: ReviewCard[], streak: int }

POST /api/review/{card_id}
Auth: Pro required
Request:  { rating: "again" | "hard" | "good" | "easy" }
Response: { card: ReviewCard, next_review_date: string }
Errors:   404, 401

POST /api/traces/{id}/share
Auth: Required (owner only)
Description: Generates or rotates the share token for a trace.
Response: { share_token: string }
```

### 7d. Third-Party Integrations


| Service          | Purpose                   | Free Tier          | Cost Risk           | Failure Handling                                                       |
| ---------------- | ------------------------- | ------------------ | ------------------- | ---------------------------------------------------------------------- |
| Ollama Cloud     | Primary explanation LLM   | Free               | $0                  | Falls back to Claude API                                               |
| Anthropic Claude | Fallback explanation LLM  | $5 credit (MVP)    | Low — fallback only | Error + retry; tracer continues without LLM                            |
| Supabase         | DB + Auth + RLS           | 500MB / 1GB        | ~$0 at MVP scale    | Tracer works unauthenticated; only persistence fails                   |
| Redis            | Distributed rate limiting | Upstash free tier  | ~$0 at MVP scale    | **Required for multi-instance** — fallback to in-memory (logs warning) |
| Vercel           | Frontend hosting          | 100GB bandwidth/mo | ~$0 at MVP          | Open source; redeploy anywhere                                         |
| Railway          | Backend hosting           | $5/month credit    | $5/month            | Tracer works without auth; only persistence fails                      |
| Stripe           | Pro billing               | No free tier       | 2.9% + $0.30/tx     | User stays on free; Stripe handles retry                               |


### 7e. Performance Targets


| Metric                               | Target                                       | Measured       |
| ------------------------------------ | -------------------------------------------- | -------------- |
| Trace generation (200-line function) | ≤ 3 seconds (server-side, excluding network) | Client timer   |
| Explanation first token (Ollama)     | ≤ 2 seconds                                  | API logger     |
| Explanation first token (Claude)     | ≤ 3 seconds                                  | API logger     |
| First Contentful Paint               | ≤ 1.5s                                       | Lighthouse     |
| Time to Interactive                  | ≤ 3s                                         | Lighthouse     |
| Concurrent users (MVP)               | ≤ 100                                        | Vercel metrics |
| Rate limit (anonymous "why")         | 20/hour (enforced server-side)               | Token bucket   |


### 7f. Security

**Execution sandbox:** Code executes on the backend server inside a subprocess with resource limits (CPU time, memory). `sys.settrace()` instruments the CPython process. Side-effect patterns (file I/O, network, subprocess) are detected and rejected before execution. The subprocess is killed after 5 seconds or after 500 trace steps, whichever comes first.

**LLM provider routing:** Ollama Cloud is the primary provider — user code is sent to `ollama.com`. Local Ollama (`localhost:11434`) is available as an optional override for users who want full privacy. Claude API is used only as a fallback.

**LLM API key:** Stored in Railway environment variables. Never exposed to browser. Claude API called server-side only.

**Auth:** Supabase Auth (JWT, HttpOnly cookies). RLS enforces data isolation: users read/write own traces only.

---

## 8. Out of Scope for V1

```
Feature: Formal research study (telemetry, study mode, evaluation pipeline)
Why deferred: Supervisor confirmed no formal study requirement. TelemetryEvent,
             TelemetrySession tables, REQ-STUDY-*, and study onboarding flow removed
             in PRD v2.0. The tool is a product demo, not a research instrument.
Target version: N/A

Feature: Pyodide / browser-side code execution
Why deferred: Replaced by backend tracer (sys.settrace()) per PRD v1.1.
             Backend tracer provides better execution control and isolation.
Target version: N/A

Feature: Multi-language support (JS, Java)
Why deferred: The custom sys.settrace() tracer only supports CPython. Supporting
             JavaScript would require a separate JS engine integration.
Target version: V2

Feature: Side-effect execution (file I/O, network, subprocess)
Why deferred: The backend subprocess sandbox limits resources but does not isolate
             the filesystem. Executing side-effect code in a shared server environment
             is a security risk. Requires Docker/gVisor isolation.
Target version: V2

Feature: Mobile responsive UI
Why deferred: Code tracing is a desktop experience. Monaco editor requires desktop.
Target version: V2

Feature: B2B / Team features (SSO, team dashboard, admin controls)
Why deferred: B2B requires SAML/SSO, multi-seat billing, and team analytics.
Target version: V3

Feature: Dark/light theme toggle
Why deferred: Dark-only is standard for developer tools.
Target version: V3

Feature: Export to Anki
Why deferred: AnkiConnect integration is a nice-to-have.
Target version: V2

Feature: Open-source tracer library (codescope/tracer)
Why deferred: After project completion, the core tracer module can be packaged as
             a pip-installable library and published to PyPI. This extends the project's
             longevity and positions it as a reusable tool.
Target version: Post-project
```

---

## 9. Success Metrics

### Primary Metric

**Trace completion rate: ≥ 80%**
Of all traces started, ≥ 80% reach the final step without abandonment.
How tracked: Supabase — trace start and completion events.
Why this metric: Completion rate directly measures whether the tracer is understandable.
Target: 30 days: 75%. 90 days: 80%.

### Leading Indicators (measurable from Week 1)

- **"Why" question rate:** ≥ 1 question per 3 traces. If < 0.33/traces: users are not finding the feature useful or don't know it exists. Fix: add tooltip or walkthrough.
- **Review queue retention:** ≥ 30% of Pro users who save a trace complete ≥ 1 review within 7 days. Measures whether the spaced repetition loop is working.
- **Return visit rate:** ≥ 40% of registered users return within 14 days. Measures ongoing value justification for account creation.

### Lagging Indicators (60–90 days)

- **Pro conversion rate:** ≥ 2% of free users upgrade to Pro. At 500 free users = 10 paying = $150/month. Viable for solo operation.
- **NPS:** ≥ 40 (survey to Pro subscribers). Below 30: immediate UX investigation required.
- **Mean helpfulness rating:** Track mean `human_rating` on explanations by pattern category. If mean drops below 3.0/5.0 for any pattern, investigate and revise the prompt.

### Anti-Metrics

```
We are NOT optimising for session length.
Long sessions may indicate confusion, not engagement.
A user who traces the same function 5 times in one session has a "good" long
session only if their pause duration per step is decreasing each time (learning).
Otherwise, they are lost.

We are NOT optimising for total traces saved.
High save rates may indicate users saving traces they don't intend to review.
The metric to watch is review completion rate (≥ 1 review per saved trace
within 7 days), not raw save count.
```

