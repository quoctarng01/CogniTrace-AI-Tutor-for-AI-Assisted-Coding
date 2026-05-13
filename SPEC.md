# CodeScope — AI Tutor for AI-Assisted Coding

## 1. Concept & Vision

CodeScope is an AI tutor that helps learners understand, verify, and remember AI-generated Python code. It grounds LLM-generated explanations in actual runtime variable state, then reinforces comprehension through spaced repetition review.

**Core framing:** Understand once. Verify it works. Remember it.

**Thesis title:** AI Tutor

**What it actually does:** When a learner pastes AI-generated code they don't fully understand, CodeScope (1) checks it for common bug patterns, (2) shows them exactly how it executes step-by-step with live variable states, (3) explains *why* it behaves that way in plain language, and (4) schedules a brief review so they actually remember it.

**Why it's non-trivial:** AI-generated code is structurally correct but semantically opaque. Learners can't tell if it's doing the right thing or just the *intended* thing. CodeScope bridges that gap by making execution visible, explanation grounded, and retention systematic.

---

## 2. Problem Statement

18–25 million developers now use AI coding assistants daily. The result: code that works but isn't fully understood by the person shipping it.

**Who feels this:**

- **Priya, CS student:** Uses Copilot to write her final project. She passes tests but can't explain her own code in code reviews. She doesn't know what she doesn't know.
- **Marcus, junior dev:** Shipped a bug caused by a Copilot suggestion. He didn't understand the edge case the code was silently handling. Now he reads every AI suggestion twice — slowly, anxiously.
- **Yuki, self-taught learner:** Uses Cursor to build projects. Learns by doing, not by studying. Accumulates patterns without understanding them deeply. Forgets what she learned within days.

**Why it happens:** AI-generated code is structurally correct but semantically opaque. The code *works*, but the learner can't trace the logic in their head. Reading the code and watching it execute are fundamentally different cognitive experiences.

**What existing tools miss:**

- Python Tutor visualizes execution but can't explain *why* the code does what it does
- Chat-based tools (ChatGPT, Copilot Chat) explain code but can't *prove* execution behavior — they guess
- Spaced repetition tools (Anki) exist for memory but have no connection to code comprehension
- None of these address the specific gap: understanding *AI-generated* code, which is structurally different from hand-written code (more edge cases, less readable, more likely to silently fail)

---

## 3. Strategic Framing

### 3.1 Thesis Contribution Statement

This thesis presents an adaptive learning system for AI-assisted coding that combines three proven techniques — runtime tracing, LLM-generated explanation, and spaced repetition — into a single coherent workflow. The contribution is not any single component, but their **integration**: explanations grounded in actual variable state, and comprehension reinforced through systematic review.

### 3.2 Why "AI Tutor" is the Right Title

"AI Tutor" names the artifact category. The thesis committee needs to understand *what* it does and *why* it's non-trivial. The abstract and introduction provide that specificity:

> This thesis presents an AI tutor for AI-assisted coding — a system that grounds LLM-generated explanations in runtime variable state, and reinforces comprehension through spaced repetition.

This is legible, defensible, and true. It doesn't need to be in the title itself.

### 3.3 Competitive Window

GitHub ships "explain this Copilot suggestion" as a sidebar panel. Cursor ships "why did my AI block do this?" Both are 12–18 months away from being competitive. CodeScope's spaced repetition review queue — the habit layer — is what incumbents can't replicate overnight. Ship the review loop before the window closes.

**Mitigation strategy:**

1. Ship Phase 2 (review queue) before GitHub ships built-in explanations
2. Build a curated example library (20-30 hand-picked patterns) that can't be replicated by pasting arbitrary code
3. Accumulate saved traces + review history as user data — switching cost grows over time

---

## 4. Technical Architecture

### 4.1 System Overview

```
[User pastes AI-generated Python code]
           ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 0: Static Analysis Layer (FREE, unlimited)        │
│  Scans for common AI bug patterns                        │
│  - Missing None checks                                    │
│  - Wrong index types                                      │
│  - Unguarded list mutations                              │
│  - Implicit type coercion risks                          │
│  Output: Inline annotation list (actionable)             │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 1: Execution Tracer (5/mo free, unlimited Pro)    │
│  sys.settrace() + bytecode analysis                      │
│  Branch detection via AST + opcode mapping                │
│  Step-by-step state capture (variables, branches, lines) │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 2: LLM Explanation Engine (Pro only)             │
│  Ollama Cloud (primary) / OpenAI (fallback)            │
│  Input: current line + variable state + branch context  │
│  Output: plain-language explanation                     │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 3: Spaced Repetition Queue (Pro only)            │
│  SM-2 scheduler                                         │
│  Saves trace + explanation as a "code fact"             │
│  Schedules review based on estimated difficulty         │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│  Review Session (daily/weekly)                           │
│  Shows code snippet + variable context                  │
│  User recalls what it does                              │
│  SM-2 updates interval based on response quality        │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Why Execution Context Matters

Standard LLM code explanations are generic. They explain *what* code typically does, not what *this specific execution* does.

CodeScope's explanations are grounded. The LLM receives:

1. The exact line being executed
2. The actual variable state at that point in execution
3. Whether this is the branch that fired or didn't fire

This produces explanations that are specific, accurate, and tied to observable runtime behavior — not guessed at.

### 4.3 Side Effect Sandboxing

The tracer runs code with `sys.settrace()`. Side effects are blocked to prevent harm:

- Imports (`import`, `__import__`) — blocked
- Network (`socket`, `requests`, `urllib`) — blocked
- File system (`open`, `os.remove`) — blocked
- System calls (`subprocess`, `os.system`) — blocked

This limits the tracer to pure computation. Pandas scripts, API clients, and file processors won't run in CodeScope. This is a known constraint. Static analysis handles these cases instead.

### 4.4 Data Flow

```
Frontend (browser)
  ├─ Code paste → API server
  │                ├─ Static analysis → annotation list → SSE → Frontend
  │                ├─ Tracer execution → step events → SSE → Frontend
  │                ├─ LLM explanation → SSE → Frontend
  │                └─ Save to database (trace + annotations + explanation)
  │
  └─ Review session → API server
                      ├─ Load queued items from database
                      ├─ Present to user
                      ├─ Record user response (Again/Hard/Good/Easy)
                      └─ Update SM-2 intervals

Database (SQLite)
  ├─ users
  ├─ traces (code, annotations, steps)
  ├─ explanations
  └─ review_queue (SM-2 state per trace)
```

### 4.5 Key Implementation Details

**Branch detection:**

```python
# Before executing a conditional block, capture the condition's truth value
# and which branch fired. Attach this as context to the next step.

def _detect_branch(frame, event, arg):
    if event == 'call':
        # Track function entry
        pass
    elif event == 'line':
        # Track each executed line
        # Detect when we're inside a branch (if/else/elif)
        # Capture the condition result that led here
        pass
    elif event == 'return':
        # Track return values
        pass
```

**Variable state capture:**

```python
# At each line event, snapshot all local variables
# Filter builtins, keep only user-defined variables
# Format for LLM: {"x": [1, 2, 3], "result": None, "count": 0}

def _capture_variables(frame):
    return {
        k: repr(v) for k, v in frame.f_locals.items()
        if not k.startswith('__') and not callable(v)
    }
```

**Cache deduplication:**

```python
# Use hash(code + line_number + variable_state) as cache key
# Avoid re-explaining the same line with the same state
# 50ms TTL on cache for fresh results on repeated calls
```

---

## 5. Product Phases

### Phase 0: Static Analysis Layer (Foundation)

**Goal:** Immediate value on every code paste — zero friction
**Deliverables:**

- Pattern scanner: 10 common AI bug patterns
  - `if x:` without `if x is not None:` (TypeError risk)
  - List comprehension without bounds check (IndexError risk)
  - `+=` on potentially undefined variable (NameError risk)
  - `==` on float (floating point precision)
  - Mutable default argument (common Python gotcha)
  - Implicit truthiness of empty collections
  - Chain comparison without parentheses
  - Unguarded `open()` without `with`
  - `requests` call without timeout
  - Missing `await` in async function
- Inline annotation display (red = bug risk, yellow = caution, green = looks fine)
- Output: actionable list, not explanation
- **Gate: FREE (unlimited)**

### Phase 1: Execution Tracer

**Goal:** Show how the code actually runs
**Deliverables:**

- `sys.settrace()` integration with sandboxing
- Step-by-step playback with animated variable state
- Branch highlighting (which `if` branch fired, why)
- "Changed variable" pulse animation
- SSE streaming to frontend
- **Gate: 5 traces/month free, unlimited Pro**

### Phase 2: LLM Explanation Engine

**Goal:** Explain *why* the code behaves this way
**Deliverables:**

- Github Model
- OpenAI API fallback
- Execution-contextual prompt (line + state + branch)
- Streaming response to frontend
- **Gate: Pro only**

### Phase 3: Spaced Repetition Review Queue

**Goal:** Make comprehension stick
**Deliverables:**

- SM-2 scheduler implementation
- Save trace + explanation as a "code fact"
- Review session UI (2-minute daily sessions)
- Response buttons: Again / Hard / Good / Easy
- Interval and ease factor tracking
- **Gate: Pro only**

### Phase 4: Curated Example Library (Competitive Moat)

**Goal:** Turn CodeScope into a learning system, not just a tool
**Deliverables:**

- 20-30 hand-picked examples of the most confusing AI-generated patterns
- Each example: code snippet + annotation + explanation + review queue entry
- Browse by category (comprehensions, async, decorators, OOP, etc.)
- "Why AI generates this" context for each pattern
- **Gate: Pro only**

---

## 6. Evaluation & Metrics

### 6.1 Thesis Evaluation Criteria

A thesis committee evaluates engineering projects on:

1. **Problem is real and non-trivial** — ✓ documented with citations
2. **Solution is technically sound** — ✓ systems programming depth demonstrated
3. **System is integrated** — ✓ tracer + LLM + SR working together
4. **Something is evaluated empirically** — need to add this

**The empirical gap:** For an engineering thesis, you need at least one quantitative evaluation. The thesis should include:


| Metric                       | Method                                           | Target                       |
| ---------------------------- | ------------------------------------------------ | ---------------------------- |
| Comprehension retention rate | 2-week follow-up quiz on 10 traced patterns      | +30% vs. control             |
| Static analysis accuracy     | Synthetic benchmark, 50 snippets with known bugs | >85% precision               |
| Review completion rate       | Track % of scheduled reviews done within 24h     | >60%                         |
| Time-to-understand           | Self-reported confidence before/after trace      | -50% self-reported confusion |


**Note:** You do not need a formal user study with IRB. Per supervisor guidance, this is an engineering project. The benchmark + self-reported metrics are sufficient for a thesis evaluation.

### 6.2 Anti-Metrics (What to Avoid Optimizing For)

- **Review completion rate** — don't add gamification that tricks users into clicking through reviews without learning
- **Trace count** — users who paste 50 snippets but review none are not engaged
- **LLM token efficiency** — accuracy matters more than cost at this stage

---

## 7. User Experience

### 7.1 Primary User Flows

**Flow 1: Paste and Verify (Priya, 2 minutes)**

```
1. Priya pastes a Copilot-generated function she doesn't fully understand
2. Static analysis runs instantly — flags 2 potential issues
3. She clicks "See how it runs"
4. Tracer animates through each step — orange pulse on changed variables
5. She sees: "At step 4, x = [1, 2] — the comprehension filtered everything out"
6. She understands. She saves it to review later.
```

**Flow 2: Daily Review (Priya, 2 minutes)**

```
1. Priya opens CodeScope, sees "3 reviews due"
2. First card: shows a code snippet she traced 2 days ago
3. She thinks about what it does, clicks "Good"
4. Next card: comprehension she reviewed yesterday
5. SM-2 schedules next review in 4 days
6. Done in 2 minutes. She's building the habit.
```

**Flow 3: Spaced Repetition at Scale (Marcus, 5 minutes)**

```
1. Marcus traces 20 Copilot suggestions over a week
2. Each one gets a scheduled review
3. After 2 weeks, he notices: the ones he reviewed consistently are patterns he now writes confidently
4. The ones he skipped — he still doesn't get
5. He realizes the review queue is working
```

### 7.2 Key UX Principles

1. **Zero friction on Phase 0.** Static analysis is instant and free. Every user gets value on the first paste.
2. **The tracer creates the aha moment.** The animation of variable state change is the emotional peak of the experience — make it smooth and clear.
3. **Reviews must be fast.** 2 minutes or less. If reviews take 5 minutes, users won't do them daily.
4. **No shame in the review queue.** The UI should feel like a trusted study tool, not a test you're failing.
5. **Explain the spacing, not just the code.** The first time a user saves a trace, briefly explain: "We'll ask you about this again in 1 day, then 3 days, then 7 days — that's how you actually remember it."

---

## 8. Go-to-Market & Pricing

### 8.1 Freemium Model


| Feature                | Free                  | Pro ($15/mo)   |
| ---------------------- | --------------------- | -------------- |
| Static analysis        | Unlimited             | Unlimited      |
| Execution tracer       | 5/month               | Unlimited      |
| LLM explanations       | —                     | Unlimited      |
| Review queue           | —                     | Unlimited      |
| Saved traces           | 20                    | Unlimited      |
| Curated examples       | —                     | 20-30 patterns |
| **Conversion trigger** | User hits trace limit | —              |


### 8.2 Conversion Path

- User pastes code → static analysis is instant and free → she sees value immediately
- User clicks "See how it runs" → tracer consumes a trace → she hits the limit at 5/month naturally
- She either waits for the reset or upgrades to Pro
- The trigger is not a sales pitch — it's a blocked action. She wants to see the next trace. The upgrade is the unlock.

### 8.3 B2B Path (6-month horizon)

Engineering teams at startups have budget and pain:

- Junior devs shipping Copilot bugs
- Need a way to onboard AI-assisted workflow
- Willing to pay per seat for tools that reduce bugs

**B2B requires:** team dashboards, SSO, GitHub integration, admin visibility. Not in V1, but plan for it.

---

## 9. Technical Stack


| Layer     | Technology                                 |
| --------- | ------------------------------------------ |
| Frontend  | React + Vite + TypeScript                  |
| Backend   | FastAPI (Python)                           |
| Tracer    | `sys.settrace()` + bytecode analysis       |
| LLM       | Ollama Cloud (primary), OpenAI (fallback)  |
| Database  | SQLite (V1) — simple, zero infra, portable |
| Hosting   | Railway (V1)                               |
| Streaming | Server-Sent Events (SSE)                   |
| Caching   | In-memory with hash-based dedup            |
| Testing   | pytest (backend), Playwright (frontend)    |


---

## 10. Risks & Mitigations


| Risk                                         | Likelihood | Impact | Mitigation                                                      |
| -------------------------------------------- | ---------- | ------ | --------------------------------------------------------------- |
| GitHub ships built-in explanations           | Medium     | High   | Ship Phase 2+3 before 18-month window                           |
| Static analysis has too many false positives | Medium     | Medium | Tune patterns on synthetic benchmark before launch              |
| Users don't complete reviews                 | High       | High   | Make reviews 2 minutes or less; first-session tutorial on SR    |
| Tracer blocks too much real code             | High       | Low    | Static analysis handles blocked code; Phase 0 is the workaround |
| Ollama Cloud goes down                       | Low        | Medium | OpenAI fallback; cache all explanations                         |
| 2% conversion is too optimistic              | Medium     | Medium | B2B path as backup; engineering team sales at $150/team/mo      |


---

## 11. What's Not in Scope

- Multi-language support (Python only — thesis scope)
- Collaborative features (shared queues, team review)
- Mobile UI (web only for V1)
- Dark mode (nice-to-have, not a launch blocker)
- Persistent sessions (SQLite, local-first is fine for thesis)
- Formal IRB-approved user study (per supervisor guidance — engineering project)

---

## 12. Milestones


| Milestone                             | Goal                                |
| ------------------------------------- | ----------------------------------- |
| M1: SPEC.md finalized                 | Council modifications applied       |
| M2: Phase 0 (Static Analysis) shipped | Users get value on first paste      |
| M3: Phase 1 (Tracer) shipped          | Core loop working end-to-end        |
| M4: Phase 2 (LLM) shipped             | Explanations grounded in execution  |
| M5: Phase 3 (SR Queue) shipped        | Habit layer activated               |
| M6: Synthetic benchmark complete      | 50 snippets, thesis evaluation data |
| M7: Beta users                        | 50 users, first conversion data     |
| M8: V1 launch                         | Public, $15/mo Pro tier             |


---

## 13. Council Modifications Applied

This SPEC.md reflects the following changes from the strategic council review:


| Change                                                          | Source        | Status               |
| --------------------------------------------------------------- | ------------- | -------------------- |
| Reframe from "tracer" to "AI tutor / adaptive learning"         | All voices    | ✅ Applied            |
| Add static analysis as Phase 0 entry point                      | SaaS Review   | ✅ Applied            |
| Update freemium gate: unlimited static analysis + 5 traces/mo   | SaaS Review   | ✅ Applied            |
| Add evaluation metrics for thesis defensibility                 | Thesis Review | ✅ Applied            |
| Define competitive window (12-18 months)                        | SaaS Review   | ✅ Applied            |
| Keep tracer architecture unchanged                              | All voices    | ✅ Confirmed          |
| Keep SM-2 and LLM pipeline unchanged                            | All voices    | ✅ Confirmed          |
| Add curated example library as Phase 4 moat                     | Critic        | ✅ Added              |
| Reposition from "educational tool" to "verification + learning" | Skeptic       | ✅ Applied in framing |


