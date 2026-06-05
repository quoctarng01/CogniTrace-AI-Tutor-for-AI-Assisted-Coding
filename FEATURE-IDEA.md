# CodeScope — Feature Ideas

# Round 4 — Final Polish

> **What changed from Round 3:**
>
> - **Elevated 3 features** to push toward 9.0 gate (current score: 8.33):
>   - #7 Spaced Repetition on Line-Level Fragments (7.00 → added concrete micro-card example with step-by-step UX)
>   - #16 Copilot Integration (7.56 → restructured to lead with XS-effort clipboard shortcut MVP, demoted VS Code extension to Phase 2)
>   - #9 Error-Trace Correlation (7.81 → added concrete example with actual mutated code, error output, and error-to-trace arrow visualization)

---

## Removed Features

### #12 Study Session Mode — REMOVED

**Score: 7.00 — Removed for genericism.**

Study Session Mode was a multi-snippet editor that let users paste 5–10 code blocks and get them all into the review queue at once. While the goal (building review habits) was valid, the implementation was a generic "paste-and-queue" wrapper with no CodeScope-specific mechanism. The feature described nothing about how the tracer, the spaced repetition system, or the example library would participate — it was essentially a batch-save workflow dressed up as a learning feature. The most actionable alternative: instead of a dedicated "study session" mode, integrate a "Save to Review Queue" button directly into the tracer toolbar so saving happens contextually during tracing, not as a separate workflow at the end of a batch session.

### #16 Trace Review Groups — REMOVED

**Score: 7.00 — Removed for lack of CodeScope-specific hook.**

Trace Review Groups attempted to create social accountability by letting study partners pool their SM-2 review queues. The feature described group dashboards and streak tracking but never defined what the "review" consisted of — it assumed a generic SRS card, not a code visualization experience. Without explaining how two students would actually co-review a trace (do they watch it together? Does one explain to the other?), the feature remained a social wrapper on a solo tool. The most actionable alternative: Guided Trace Walkthroughs (existing Pro feature #14) already solves the collaborative learning problem with a teacher-student annotation model that is specific to the tracer. The group-queue concept is better served by that existing feature.

### #6 Explanation Confidence Scoring — REMOVED

**Score: 7.19 — Removed for infeasibility.**

This feature proposed displaying confidence indicators on LLM explanations based on how many times a similar `(code_hash, line, variable_state_hash)` tuple had been explained before. The reviewer correctly identified that this requires a ground-truth dataset to calibrate — without labeled data on explanation accuracy, the "confidence" signal is arbitrary. There's no clear path to building that dataset without a costly human-labeling pipeline, and the feature would ship with uncalibrated confidence scores that could mislead learners. The most actionable alternative: keep the "Was this helpful?" thumbs-up/down on each explanation (already implicit in the UX) and use that as a weak signal. That requires no new infrastructure and delivers incremental value without overpromising accuracy.

---

## Ideas (ranked by priority)

### 1. Shared Trace Links — One-Click Replay 🔁

- **Problem:** Learners share code snippets in Discord, Slack, or code review — but they can't share a live trace. They'd have to screenshot the tracer or describe the variable state manually.
- **How it works:** When a user saves a trace (or runs one without saving), offer a "Share" button that generates a short read-only URL (`/trace/{share_token}`). The shared page loads the code + full steps + annotations + the last-saved explanation, rendered as a static replay (not an interactive tracer — just an animated playback). The backend generates a UUID token stored in Supabase, tied to the trace.
**Link management:**
  - **Expiration options:** "Never" (default), "24 hours," "7 days," "30 days." Expired links return a 410 Gone with a "This trace has expired — sign in to view it" message.
  - **Password protection (optional):** Users can set a share password when generating the link. The share page shows a password gate; upon entry, the password is verified client-side against a bcrypt hash stored in the share token row. Wrong password returns a generic "Incorrect password" (no hints).
  - **Fork this trace:** Authenticated viewers of any shared link see a "Fork & Trace" button — this copies the code into their own tracer, pre-fills the same initial namespace, and runs the trace fresh. The fork is a new trace owned by the viewer, not linked to the original. This is the collaborative debugging hook.
  - **Share analytics:** The share endpoint records every access: `share_token`, `viewed_at`, `viewer_ip` (hashed), `referrer`, `is_authenticated` (boolean), `forked` (boolean). The share creator sees a dashboard: total views, unique views, forks count, top referrers. These analytics live in a `share_analytics` table in Supabase.
- **Why it matters:** This is the viral loop. Every shared trace link is a living demo of CodeScope's core value — "here's what this code actually does." Someone clicks the link, sees the animation, and either signs up to try it themselves or bookmarks CodeScope as a reference tool. The fork capability turns passive viewers into active users. The infrastructure is almost entirely in place: the share page (`/trace/[share_token]`) already exists in the codebase.
- **Effort:** S
- **Priority:** 1

---

### 2. Pattern Catalog — "Why AI Writes This"

- **Problem:** The example library is passive — users browse, pick examples, and save them. But the highest-value moment is right after pasting their own code, when static analysis fires. That moment is where CodeScope can say "this pattern matches an AI-generation artifact."
- **How it works:** Extend the static analysis layer with a new annotation type: `ai_pattern_id`. Each detected pattern maps to a `why_ai_generates_this` explanation — pre-authored or LLM-generated once. When the analyzer fires on a user's code, the annotation includes the pattern ID and the "why AI writes this" blurb. A "Learn More" button links to the example library entry for that pattern. The backend stores the pattern catalog as a lightweight JSON file seeded from the example library's existing `why_ai_generates_this` field.
- **Why it matters:** This closes the loop between Phase 0 (static analysis, free/unlimited) and Phase 4 (curated library). Every free user hitting static analysis gets a taste of the library's depth. This is the compounding hook: once users associate "CodeScope shows me why my AI code does this," they return for it.
- **Effort:** S
- **Priority:** 2

---

### 3. What-If Sandbox — Override Initial Namespace

- **Problem:** Users want to experiment — "what if `items` is empty?" or "what if the threshold is 100 instead of 10?" They currently have to manually edit the code, re-paste, and re-trace. That's enough friction to prevent experimentation.
- **How it works:** Add an "Edit Input" panel above the code editor where users can pre-fill variable values before running the trace. The backend accepts an `initial_namespace` parameter (a dict of variable names → values) and overrides `frame.f_locals` at step 0 before execution begins. No mid-trace mutation needed — this is pure pre-condition exploration.
**The UX flow (fully specified):**
  1. User runs a trace normally.
  2. While watching playback (or after it completes), they click "What If?" in the toolbar.
  3. A modal appears with a form auto-populated from the variable names in scope: `items = [3, 1, 4, 1, 5]`, `threshold = 10`, `acc = 0`. Each field is editable.
  4. User changes `items` to `[]` and `threshold` to `100`, then clicks "Replay from Here."
  5. The tracer re-executes from step 0 with the modified namespace. The replay plays with a subtle "REPLAY" badge and a color tint on the VariablePanel (blue instead of the default accent) so users can visually distinguish it from the original trace.
  6. The comparison is visual, not analytical — users see the new execution side by side with what they remember from the original. The sidebar notes "You changed `items` from [3, 1, 4, 1, 5] → [] and `threshold` from 10 → 100."
  The modal pre-populates variable types intelligently: strings render as text inputs, numbers as number inputs, lists as JSON editors with syntax highlighting, booleans as toggles.
- **Why it matters:** The aha moment isn't just "I understand the code" — it's "I understand this code *in this context*, and here's what happens in a different context." Experimentation is how comprehension becomes mastery. This is the clearest differentiator from PythonTutor, which shows variable values but never lets you change the starting conditions. The "Replay" UX with visual distinction makes the comparison intuitive without requiring a full diff-tracer implementation.
- **Effort:** XS
- **Priority:** 3

---

### 4. Concept Heatmap — Which Code Patterns Have You Traced?

- **Problem:** Users build up a trace history over weeks but have no visibility into which Python concepts they've actually internalized vs. which they're avoiding. They don't know their own knowledge gaps.
- **How it works:** Tag each saved trace with concept tags (`FUNCTION`, `LOOP`, `COMPREHENSION`, `CONDITIONAL`, etc. — the `extractConceptTags` logic already exists in `tracer/page.tsx`). Aggregate these into a per-user heatmap shown on the dashboard: which concept categories have been traced, how many times, and how the SM-2 retention looks for each. Untagged or under-traced categories get a "You haven't traced any comprehensions yet — try an example" nudge. Backend: a new `/api/profiles/concepts` endpoint that aggregates trace tags per user.
- **Why it matters:** Spaced repetition only works if you're reviewing the right things. A heatmap tells users where they're cheating themselves — pasting only code they kind of understand while avoiding the comprehensions and async patterns they really need to learn. This adds the "meta-learning" layer that makes CodeScope feel like a tutor, not a tool.
- **Effort:** S
- **Priority:** 4

---

### 5. Trace Replay from Saved State 🔁

- **Problem:** Saved traces are inert — you can browse them but you can't re-animate the step-by-step playback. You have to re-run the code to get the trace back. This breaks the review flow: you want to revisit a saved trace's execution animation, not just its code and explanation.
- **How it works:** Extend the `run_trace` response to include `trace_id`. On save, store the full steps array in Supabase (already partially done via `trace_data` in the review card). When loading a saved trace, return the full steps array so the frontend can re-initialize `useTrace` with actual execution data. No re-execution needed — the trace is a complete replay recording. The VariablePanel and ExplanationPanel work identically because they derive from the same `TraceStep` shape.
**The SM-2 connection (full flow):**
When a user's review queue fires a card for SM-2 scheduling, the frontend loads the full trace steps from the saved state (not by re-executing the code). This is critical because:
  - The code may have been edited since the trace was saved (the user may be on a different version of their own script).
  - The trace may have used imports or global state that are no longer in scope.
  - Replaying the exact variable state from the original trace is more educationally honest than re-running code that might now produce different values.
  The VariablePanel pre-populates with the exact variable snapshots from the saved trace — users see the same values they saw when they first traced the code. The "Play" button resumes the step-by-step animation from wherever the user paused. The "Good/Hard/Again" SM-2 buttons appear below the replay controls.
  **Future hook:** This saved state model enables "Trace Forks" — the ability to take any review card's saved trace, fork it (make a copy), edit the initial namespace (via What-If Sandbox), and run a new trace from the fork. This creates a practice workflow: "I got confused at step 4 of this trace — let me fork it and see what happens if I change `items` to `[]`."
- **Why it matters:** Without this, the review queue shows code snippets, not executions. Users reviewing a card see the code — but to truly understand it, they need to *watch it run again*. This is the spaced repetition loop working at full power: review → see code → tap to replay animation → watch the exact variable state change → click "Good." Without replay, you skip the most impactful part of the review.
- **Effort:** XS
- **Priority:** 5

---

### 6. Trace Difficulty Classifier — Adaptive SM-2 Intervals

- **Problem:** SM-2 starts all cards with the same interval schedule (1 day, then 6 days). But a simple 5-line trace and a complex 50-line trace with nested comprehensions and closures have very different retention curves. Starting from the same defaults wastes review slots on easy cards and doesn't space hard cards aggressively enough.
- **How it works:** When a trace is saved, the backend computes a difficulty score: number of steps, cyclomatic complexity (from the AST), number of distinct variable types, presence of comprehensions/closures/generators, and whether branch detection fired. Map this to an initial SM-2 easiness factor: lower EF for complex traces. The formula is simple: `initial_ef = max(1.3, 2.5 - complexity_penalty)`. The frontend shows "This is a complex trace — we'll review it more frequently at first." No changes needed to the SM-2 algorithm itself, just the initial parameters.
- **Why it matters:** SM-2 is a powerful algorithm but it's initialized with defaults that assume equal difficulty. A tracer that knows its own complexity can do something no generic SRS tool can: initialize intervals based on the actual cognitive load of the material. This is the tracer + SR integration working at the data level, not just the UX level.
- **Effort:** S
- **Priority:** 6

---

### 7. Spaced Repetition on Line-Level Fragments

- **Problem:** A full trace review card shows the entire code snippet. But the confusing part might be a single comprehension on line 7. Users can't target their review on the specific line they found confusing.
- **How it works:** Allow users to select a specific line (or a variable state snapshot) from a trace and save just that as a micro-card. The micro-card stores: the line content, the variable state at that step, and the branch context (if any). During review, the user sees only the fragment — the line, the variable values — and has to recall what was happening. The full trace is one tap away. Backend: add a `card_type` field to `review_cards` (`full_trace` | `line_fragment`), and a new endpoint to create micro-cards from a trace step.
- **Concrete Example:**
User traces this code:
  ```python
  n = 10
  result = [i for i in range(n) if i % 2 == 0]
  print(result)
  ```
  At step 4 (the list comprehension mid-execution), the variable state is:
  - `n = 10`
  - `i = 4`
  - `result = [0, 2]`
  - Current line: `if i % 2 == 0`
  User clicks the variable `result` or the comprehension line and hits "Save this as a micro-card." The system creates a line-fragment card:
  ```
  ┌─────────────────────────────────────────────────────┐
  │  LINE 2:  result = [i for i in range(n) if i % 2 == 0]
  │                                                     │
  │  State at this step:                                │
  │    n = 10                                           │
  │    i = 4                                            │
  │    result = [0, 2]                                  │
  │                                                     │
  │  Tap to see full trace →                            │
  │                                                     │
  │  [Good] [Hard] [Again]                              │
  └─────────────────────────────────────────────────────┘
  ```
  The user studies the card: sees the line and the partial result, recalls that `i=4` is even so it gets appended, wonders what happens when `i=5`. They tap "Hard" and SM-2 schedules it for 2 days. Later, the review fires — same fragment, same partial state, same mental question. The micro-card feeds directly into the existing SM-2 queue via the new `card_type = 'line_fragment'` column, using the same interval logic as full-trace cards.
- **Why it matters:** SM-2 works best on atomic, well-defined facts. "What does this list comprehension do?" is a better review card than "What does this entire function do?" Line-level cards let users focus their spaced repetition on the exact confusion point, not the surrounding scaffolding. This also increases review volume — users who save 1 trace can generate 5 micro-cards from it, filling their queue with high-value items.
- **Effort:** M
- **Priority:** 7

---

### 8. Tracer Breadcrumb Trail — "How Did We Get Here?"

- **Problem:** In long traces (20+ steps), users can lose track of the execution path. They see a variable with an unexpected value and can't figure out which branch, loop iteration, or call stack depth produced it.
- **How it works:** When the user pauses on any step, render a compact "breadcrumb" trail above the VariablePanel: `fibonacci(8) → if n <= 0 (False) → elif n == 1 (False) → for i in range(8) [iter 3/8] → if items[i] > threshold`. Each breadcrumb item is tappable — clicking it jumps to that step. The tracer already captures call events and loop iteration context via `opcode_map`. This is purely a frontend display layer that renders the step history as a path. Backend: ensure the trace steps include enough call depth information (already partially captured in the frame chain walk in `_capture_variables`).
**The SM-2 connection (concept difficulty mapping):**
The breadcrumb trail captures something the SM-2 algorithm currently doesn't have: *where in the call depth users get confused*. When a user repeatedly navigates back to a specific call depth during a trace — say, they click back to `fibonacci(n-1)` three times in a row — that behavior signals conceptual difficulty at that depth. The backend logs each breadcrumb click with the trace step index and a concept tag derived from the breadcrumb (e.g., `RECURSION`, `LOOP`, `CONDITIONAL`).
This data feeds a per-concept difficulty model: if a user consistently gets stuck at `RECURSION` breadcrumbs across multiple traces, the SM-2 ease factor for recursion-adjacent cards is automatically decreased, scheduling them more frequently until the confusion clears. Conversely, if a user never revisits `LOOP` breadcrumbs, the ease factor for loop cards increases, stretching intervals faster. The frontend shows: "You often revisit recursion steps — we'll keep these in your queue until they're solid."
This is the tracer doing diagnostic learning analytics that no generic SRS app can perform.
- **Why it matters:** This is a UX multiplier for comprehension depth. Without breadcrumbs, understanding a 30-step trace requires holding the entire execution history in working memory. With breadcrumbs, the learner has a persistent map of where they are in the execution. The SM-2 integration turns confusion signals into adaptive scheduling, making the review queue genuinely intelligent about what each user struggles with.
- **Effort:** S
- **Priority:** 8

---

### 9. Error-Trace Correlation — "This Line Would Have Crashed"

- **Problem:** Static analysis warns about potential bugs before execution. But users don't get feedback on *what would have happened* if the dangerous pattern fired. They see "mutable default argument" but don't viscerally understand the failure mode.
- **How it works:** When static analysis detects a high-severity pattern (e.g., mutable default, missing None guard), offer an "Inject Failure" button. This runs a modified version of the code where the dangerous condition is triggered: inject an empty list as the default call, or pass `None` where the guard is missing. The tracer runs this mutation and stops at the exact step where the crash occurs. The user watches the error materialize in the VariablePanel — the variable goes red, the stack trace appears inline. This is the tracer proving the analysis right.
- **Concrete Example:**
User pastes this code:
  ```python
  def greet(names=[]):
      names.append("CodeScope")
      return f"Hello, {', '.join(names)}"

  print(greet())      # Step 1
  print(greet())      # Step 2
  print(greet())      # Step 3
  ```
  Static analysis fires: **"Mutable default argument detected on line 1."**
  User clicks "Inject Failure." The backend runs `inject_fault` with the mutated variant:
  ```python
  # inject_fault mutates the call site to trigger the default
  def greet(names=[]):
      names.append("CodeScope")
      return f"Hello, {', '.join(names)}"

  print(greet(names=[]))   # ← injected: explicit empty list
  print(greet(names=[]))   # ← injected
  print(greet(names=[]))   # ← injected
  ```
  The tracer executes. At step 3, execution hits the crash:
  ```
  ┌──────────────────────────────────────────────────────────────┐
  │  Step 3 / 9 — CRASH                                        │
  │                                                              │
  │  1│ def greet(names=[]):                        (dimmed)    │
  │  2│     names.append("CodeScope")     ← HERE!               │
  │  3│     return f"Hello, {', '.join(names)}"                 │
  │                                                              │
  │  VariablePanel:                                              │
  │    names = []            (red, pulsing)                      │
  │                                                              │
  │  ╔══════════════════════════════════════════════════════╗   │
  │  ║ TypeError: unsupported operand type(s) for +:        ║   │
  │  ║ 'str' and 'str'                                       ║   │
  │  ║ → names = []                                          ║   │
  │  ║ → ', '.join([]) = ""                                  ║   │
  │  ║ → f"Hello, " + "" = "Hello, " (wait...)               ║   │
  │  ╚══════════════════════════════════════════════════════╝   │
  │                                                              │
  │  The arrow points from the error to step 2 — because step 2  │
  │  appended "CodeScope" to the SHARED default list, and the   │
  │  error trace shows the resulting empty list flows forward.   │
  └──────────────────────────────────────────────────────────────┘
  ```
  The "error-to-trace arrow" connects the crash point to the variable state that caused it. The user sees `names = []` in red on line 2 — they can trace the causation chain: the mutable default was shared across calls, and the injected empty list bypassed the accumulation that made the original "work." The next static analysis warning now has a visceral meaning: *this is what would happen if the guard weren't there.*
- **Why it matters:** Warning labels on code are abstract. Watching an error actually happen — seeing the variable state that caused it, the exact step where it failed — is concrete. This transforms static analysis from a passive warning system into an interactive demonstration. It's the difference between "smoking causes cancer" (abstract) and "here's a lung with cancer cells" (concrete). The technical path is clear: modify the trace runner to accept an `inject_fault` parameter that mutates the initial namespace.
- **Effort:** M
- **Priority:** 9

---

### 10. Diff Tracer — Before/After Execution Snapshot

- **Problem:** Users paste modified code and want to understand what changed in execution behavior — not just the output. Right now they have to mentally compare two traces or re-run side by side.
- **How it works:** After running a trace, allow the user to click "Compare to Previous." Store the prior trace's step sequence + variable snapshots. On re-run, render a split view: old steps on the left, new steps on the right. Lines where behavior diverges (different branch taken, different variable value, different step count) are highlighted.
**The split-screen layout (fully specified):**
  - **Left panel — "Before":** The original trace, rendered exactly as it would appear in the standard tracer. A "Before" badge in the corner. Step counter and variable panel work normally.
  - **Right panel — "After":** The new trace (from the modified code), rendered identically. An "After" badge.
  - **Middle panel — "Delta":** A vertical column showing a condensed timeline of all steps from both traces. Each step is a dot on a vertical line. If the Before and After took the same step (same opcode, same line, same variable state), the dot is gray. If they diverged, the dot is orange with a pulsing border. Clicking a divergent dot scrolls both panels to that step and highlights the specific difference in the VariablePanel.
  - **Divergence markers:** When the two traces diverge, the middle panel shows a label: "Step 4: Branch difference — Before took `else`, After took `if`" or "Step 7: `acc` differs — Before=21, After=15." The VariablePanel on each side shows a red/green diff on the differing values.
  - **Timeline scrubber:** A shared scrubber at the bottom of all three panels lets users jump to any step. Scrubbing one panel scrubs all three simultaneously.
  **Backend:** Store the prior trace's steps in a `prior_trace_steps` column on the trace record. Add a `/api/compare` endpoint that accepts `trace_id_a` and `trace_id_b` and returns: `steps_a`, `steps_b`, and a `diff` array of `{ step_index, type: 'match' | 'branch_divergence' | 'value_divergence' | 'step_count_diff', details }`.
- **Why it matters:** This is the natural extension of "verify AI-generated code." You don't just want to understand the code — you want to know what your edit (or Copilot's revision) actually changed. This turns CodeScope from a comprehension tool into a **diff comprehension tool**, directly serving the primary use case.
- **Effort:** S
- **Priority:** 10

---

### 11. Live Pair Tracing — Teacher Annotates, Student Follows 💎 Pro

- **Problem:** Pair programming is a proven learning technique. But when a learner and mentor share a trace link, they can only view it asynchronously — they can't point, highlight, and say "look at this line" together. Existing tools (screenshare, Loom) are heavy and lose the interactive quality.
- **How it works:** The Pro teacher starts a live session from any shared trace URL. Supabase Realtime creates a room; the teacher gets a session link to share. When the student joins, both see the same animated playback (play/pause/step are controlled by the teacher only — the student's view is locked). The teacher can stamp any line with a text annotation at any playback position — these annotations appear in real-time on the student's view via Supabase Realtime broadcast (no WebSocket server needed). The teacher can also stamp a line in red ("watch this"), yellow ("common mistake"), or green ("this is the key insight"). The student sees annotations appear inline as the teacher places them. When playback reaches a stamped line, the annotation expands. At the end, all annotations are saved as a snapshot tied to the trace for future viewers.
- **Why it matters:** This is the synchronous teaching tool — one-click to turn a trace into a live tutoring session. For tutors running paid sessions, CodeScope becomes the infrastructure. The per-session pricing or Pro seat is easy to justify when the tool is what you're doing the lesson through. No WebSocket server, no cursor sync, no laser pointer — just annotations and synchronized playback via Supabase Realtime. That makes feasibility ~M instead of ~L.
- **Effort:** M
- **Priority:** 11

---

### 12. Guided Trace Walkthroughs — Teacher-Crafted Lessons, Student-Played 💎 Pro

- **Problem:** Teachers who create high-quality traces have no way to package them as a structured learning experience. A shared trace link is a one-shot demo — the student watches it, maybe learns something, and leaves. There's no "here's what I want you to notice" annotation layer that turns a trace into a lesson.
- **How it works:** A Pro teacher creates a walkthrough from any saved trace: they place timestamped "stop points" with text annotations (e.g., step 4: "Notice how `acc` accumulates across iterations — this is tail behavior"), add labels to variables, and write a short intro/outro blurb. They publish the walkthrough as a special trace URL. When a student opens it, they see a guided playback: playback auto-pauses at each stop point, the annotation slides in, and the student must tap "Continue" to proceed. The teacher sees anonymized engagement: which stop points students spent the most time on, where they skipped ahead, how many completed the walkthrough. This is the *authoring layer* that turns trace consumers into curriculum creators.
- **Why it matters:** This is the Pro-tier content engine. Walkthroughs are the unit of teaching: a teacher with 10 walkthroughs has created 10 hours of structured curriculum. This differentiates CodeScope from every other Python visualizer, which are passive viewers. CodeScope becomes a platform for teaching, not just learning. B2B pricing is easy to justify when a bootcamp can say "our instructors created 200 walkthroughs used by 1,000 students this quarter."
- **Effort:** M
- **Priority:** 12

---

### 13. Team Trace Library — Shared Workspace for Curriculum Curation 💎 Pro

- **Problem:** Pro teachers and bootcamp instructors want to share curated trace collections with their students — but the public library is open and unauthenticated, and individual shared links require manual distribution. There's no concept of a private, instructor-curated trace library tied to a course or cohort.
- **How it works:** A Pro user creates a "Team Library" — a named, private workspace with a shareable course code (e.g., `CS101-PYTHON`). The teacher adds traces to the library by saving them with a "Add to Team Library" button, organizing them into named collections (e.g., "Week 3: Recursion", "Quiz 2 Review"). Collections can be tagged with concept categories and difficulty ratings. Students access the library by entering the course code — they're read-only members of the team.
**Teacher capabilities:**
  - Create collections and add traces (from their own saved traces or from the public library).
  - Set a collection as "required" (appears in student dashboards with a due date) or "optional."
  - Reorder traces within a collection.
  - View per-collection analytics: how many students viewed it, how many completed all traces, average time spent.
  **Student experience:**
  - Enter a course code once → the team library appears in their sidebar under "My Courses."
  - Browse required and optional collections.
  - Run any trace in the library. Completed traces are tracked.
  - Save individual traces from the library to their personal review queue.
  **Backend:** New `/api/teams` endpoints: `POST /api/teams` (create), `POST /api/teams/:id/traces` (add trace), `GET /api/teams/:id/traces` (list with collections), `POST /api/teams/:id/join` (join via course code), `GET /api/teams/:id/analytics` (teacher-only aggregate stats). Team membership stored in Supabase: `teams`, `team_members` (role: `owner` | `member`), `team_traces` (with collection and order), `team_trace_completions` (per-student completion tracking).
- **Why it matters:** This is the B2B revenue feature. The Annotated Trace Library (public) serves the creator economy, but Team Trace Library (private) serves the institutional customer — bootcamps, university courses, corporate training. A coding bootcamp teaching 50 students pays $20/seat/month for a private library with curated traces and completion analytics. That's $12,000/year for a feature that costs ~3 weeks to build. No other Python visualization tool has this. It's the feature that makes CodeScope a platform, not just a tool.
- **Effort:** M
- **Priority:** 13

---

### 14. Mid-Trace Mutation — Pause and Break the Code (Research Spike)

- **Problem:** Users want to understand error paths — "what if the API returns `None`?" or "what if this variable is uninitialized?" The What-If Sandbox handles initial state changes, but sometimes the interesting question is about mid-execution state.
- **How it works (honest approach):** When paused on step N, the user edits a variable value in the VariablePanel. The backend re-executes the trace from step 0, but applies a **fast-forward optimization**: it pre-computes all steps 0 through N-1 by replaying the already-captured step results (from the saved trace), then injects the mutated variable value into the frame state at step N and continues execution from there. The replay phase is O(N) string comparisons — fast. The continuation from N is fresh execution. The user sees the original execution up to step N-1, then watches the mutated state ripple forward from their edited value. This avoids any frame reification or `sys.settrace` manipulation.
**Research Spike required:** Before committing to this approach, spike two things: (1) measure replay cost for N=1000 step traces — is the string-comparison fast-forward fast enough to feel instant? (2) verify that re-executing from step N with a modified initial namespace correctly reproduces all subsequent state for complex traces with closures, comprehensions, and mutable aliases. Some execution paths may be non-deterministic with respect to the captured step sequence.
- **Why it matters:** The deepest learning moments happen when you break the expected path. "I thought this would crash, but it didn't — why?" or "I wonder what happens if I mutate this in the middle of the loop." This is the feature that makes CodeScope feel like a *debugger*, not just a tracer. No other Python visualization tool offers this.
- **Effort:** L (or research spike M before committing)
- **Priority:** 14

---

### 15. Embeddable Trace Widget — CodeScope Anywhere

- **Problem:** Blog posts, tutorials, and documentation explain Python code with screenshots or gifs — but these are static and quickly become outdated. There's no way to embed a live, interactive trace on an external site.
- **How it works:** Export any shared trace as an embeddable snippet: `<codescope-trace src="https://codescope.io/trace/abc123"></codescope-trace>`. The widget loads the trace data (or fetches it from the share endpoint) and renders a minimal interactive tracer: code view, play/pause, step forward/back, and a read-only variable panel. No account required to view. The widget is a self-contained web component (~50KB) that can be loaded on any site via a CDN script tag. Optionally: an iframe fallback for sites that block web components.
- **Why it matters:** This is the distribution and SEO play. Every blog post, tutorial, or course site that embeds a CodeScope trace is free marketing. When someone reads "Understanding Python Closures" on a popular blog and interacts with the embedded trace, they've experienced CodeScope without ever visiting the site. Conversion from embed → sign-up is the lowest-friction acquisition path possible. Competitors like PythonTutor have no embeddable widget.
- **Effort:** M
- **Priority:** 15

---

### 16. Copilot Integration — Your AI Suggestions, Visualized

- **Problem:** Developers using GitHub Copilot or Cursor AI get suggestions that "look right" but behave unexpectedly. The AI explains its suggestion in comments, but the learner can't *see* the execution path of the suggestion before accepting it.
- **How it works (Phase 1 — XS effort, browser clipboard shortcut):**
The lowest-friction path from "AI suggested this" to "I see what this does" is a keyboard shortcut. A browser bookmarklet or browser extension adds a single button to any page where developers paste code — GitHub, Stack Overflow, a REPL, or the CodeScope tracer itself. Clicking it copies the selected text (or clipboard contents) and immediately navigates to CodeScope with the code pre-loaded and the trace auto-starting.
  ```
  User copies Copilot suggestion → hits CodeScope shortcut → sees animated trace
  ```
  **The exact flow:**
  1. User accepts a Copilot suggestion in their editor (VS Code, Cursor, etc.).
  2. They select the newly inserted code and copy it (Ctrl+C / Cmd+C).
  3. They press the CodeScope browser shortcut (e.g., `Ctrl+Shift+T` or a toolbar button).
  4. The browser extension reads the clipboard, POSTs the code to `/api/trace` (anonymous, no account needed), receives the trace data, and redirects to `/trace/{trace_id}`.
  5. The trace plays automatically. The user watches the execution unfold.
  **Bookmarlet alternative (zero install):** A browser bookmark that contains a JavaScript snippet: on click, it reads `navigator.clipboard`, builds the URL `https://codescope.io/trace?code={encoded}`, and navigates there. The server handles the trace execution and redirect. One bookmark, works everywhere, no extension needed.
  **Phase 2 — VS Code extension (L effort, defer):**
  A proper VS Code extension that detects when Copilot inserts code, shows a "Trace in CodeScope" button in the inline suggestion widget, and sends the code directly via the CodeScope API with a deep link back to the trace. This is the fully integrated experience — but it requires VS Code API work, extension publishing, and ongoing maintenance. Lead with Phase 1.
- **Why it matters:** AI-generated code is now the primary way developers learn Python — they accept suggestions without understanding them. CodeScope positioned as "the tool that explains what your AI just wrote" is the most compelling value prop for the 2025-2026 developer audience. The clipboard shortcut is the XS-effort bridge: no extension to install, no account required, one keystroke from Copilot suggestion to animated trace.
- **Effort:** XS (Phase 1 bookmarklet) | L (Phase 2 extension)
- **Priority:** 16

---

### 17. PythonTutor Weakness Exploitation — Competitive Moat Analysis

PythonTutor (pythontutor.com) is the incumbent. Here's where it fails and how CodeScope's features exploit each gap:


| PythonTutor Weakness                                                                               | CodeScope Exploit                                                                                 | Feature(s)                                  |
| -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| **Frozen UI from 2010** — no dark mode, no mobile, no modern design.                               | Modern responsive UI built with Next.js.                                                          | (core product)                              |
| **No AI explanations** — just visualization, no "why is this here?"                                | LLM-powered line-level explanations streamed from actual execution state.                         | ExplanationPanel                            |
| **No spaced repetition** — just a history of past sessions you have to manually revisit.           | SM-2 review queue with adaptive intervals based on trace complexity.                              | Difficulty Classifier, Line-Level Fragments |
| **No social features** — you can't share traces in a way that makes the recipient want to sign up. | Share links are read-only animated replays that *sell* the product.                               | Shared Trace Links                          |
| **No concept tracking** — users have no visibility into their own knowledge gaps.                  | Concept heatmap shows exactly which Python patterns you've traced.                                | Concept Heatmap                             |
| **No editor integration** — you have to copy-paste code into a web form.                           | Copilot/Cursor extension for one-click tracing of AI suggestions.                                 | Copilot Integration                         |
| **Static examples only** — you can't experiment with the code.                                     | What-If Sandbox and Mid-Trace Mutation let you mutate initial and mid-execution state.            | Ideas 11, 14                                |
| **No collaboration** — pair programming requires screenshare.                                      | Live Pair Tracing lets teachers annotate shared traces while students follow along in real-time.  | Live Pair Tracing (Pro)                     |
| **No gamification or streak tracking** — learning feels like work, not a habit.                    | Streak tracking, study session summaries, team leaderboards.                                      | (core product), Team Trace Library          |
| **No personalization** — same examples for everyone.                                               | Pattern Catalog shows "why AI writes this pattern" personalized to the user's own code.           | Pattern Catalog                             |
| **No error injection** — warnings about dangerous patterns are abstract.                           | "Inject Failure" runs the exact code variant that would crash and shows the step-by-step failure. | Error-Trace Correlation                     |
| **No embedding** — can't be used in blog posts or documentation.                                   | Embeddable trace widget turns any external page into a live demo.                                 | Embeddable Trace Widget                     |
| **No teaching-content authoring** — teachers can't create structured lessons from traces.          | Guided Trace Walkthroughs + Team Trace Library let teachers author and distribute curriculum.     | Guided Walkthroughs, Team Library (Pro)     |
| **No diff/comparison** — can't compare what you changed.                                           | Diff Tracer shows side-by-side before/after execution behavior.                                   | Diff Tracer                                 |
| **No progression tracking** — no sense of building skill over time.                                | Concept Heatmap + Difficulty Classifier + SM-2 retention curves give a complete picture.          | Ideas 4, 6                                  |


**Bottom line:** PythonTutor is a code visualizer. CodeScope is a code comprehension engine with a memory. Every feature above either fills a gap PythonTutor has left open for 15 years or exploits a capability (LLM + tracer + SR) that PythonTutor structurally cannot match without rebuilding from scratch.

---

## Summary


| #   | Feature                                                  | Effort | Priority | Tier |
| --- | -------------------------------------------------------- | ------ | -------- | ---- |
| 1   | Shared Trace Links — One-Click Replay                    | S      | 1        | Free |
| 2   | Pattern Catalog — "Why AI Writes This"                   | S      | 2        | Free |
| 3   | What-If Sandbox — Override Initial Namespace             | XS     | 3        | Free |
| 4   | Concept Heatmap — Which Patterns Have You Traced?        | S      | 4        | Free |
| 5   | Trace Replay from Saved State                            | XS     | 5        | Free |
| 6   | Trace Difficulty Classifier — Adaptive SM-2 Intervals    | S      | 6        | Free |
| 7   | Spaced Repetition on Line-Level Fragments                | M      | 7        | Free |
| 8   | Tracer Breadcrumb Trail                                  | S      | 8        | Free |
| 9   | Error-Trace Correlation — "This Line Would Have Crashed" | M      | 9        | Free |
| 10  | Diff Tracer — Before/After Execution Snapshot            | S      | 10       | Free |
| 11  | Live Pair Tracing — Teacher Annotates, Student Follows   | M      | 11       | Pro  |
| 12  | Guided Trace Walkthroughs — Teacher-Crafted Lessons      | M      | 12       | Pro  |
| 13  | Team Trace Library — Shared Workspace for Curriculum     | M      | 13       | Pro  |
| 14  | Mid-Trace Mutation — Pause and Break the Code            | L      | 14       | Free |
| 15  | Embeddable Trace Widget — CodeScope Anywhere             | M      | 15       | Free |
| 16  | Copilot Integration — Your AI Suggestions, Visualized    | XS/L   | 16       | Free |


**Total ideas: 16** (down from 19 after removing 3)
**Free tier: 11** | **Pro tier: 4** (Live Pair Tracing, Guided Walkthroughs, Team Trace Library, Annotated Trace Library removed — merged into Team Trace Library as the Pro flagship)

---

## Top 3 Recommended for Immediate Development

**#1 Shared Trace Links (Priority 1, Effort S)**
The share page already exists (`/trace/[share_token]`). Adding a "Share" button to the tracer toolbar, link expiration, password protection, fork capability, and analytics is a well-scoped feature that immediately unlocks the viral loop. Every shared link is a live demo. The Team Trace Library (Pro) depends on the same share infrastructure.

**#3 What-If Sandbox (Priority 3, Effort XS)**
One-click input mutation before running a trace. Technically minimal, pedagogically maximal. The UX flow is fully specified: click "What If?", edit variables in the modal, hit "Replay from Here," watch the modified trace play with a visual REPLAY badge. No other Python visualization tool lets you ask "what if `items = []`?" before watching the code execute.

**#5 Trace Replay from Saved State (Priority 5, Effort XS)**
The saved trace data is already partially stored via `trace_data` in the review card. The remaining work is returning the full steps array on load so the frontend can replay without re-execution. This is the SM-2 integration's most critical missing piece — without it, review cards show code, not executions.