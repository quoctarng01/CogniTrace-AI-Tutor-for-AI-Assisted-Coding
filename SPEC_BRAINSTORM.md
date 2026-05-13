# CodeScope — AI Tutor for AI-Assisted Coding

---

## 1. Problem

18–25 million developers use AI coding assistants daily. The result: code that *works* but isn't fully understood by the person shipping it.

**Why it happens:** AI-generated code is structurally correct but semantically opaque. Learners can't trace the logic in their head. Reading code and watching it execute are fundamentally different cognitive experiences.

**Who feels this:**

- CS students who pass tests but can't explain their own code
- Junior devs who shipped a bug from a Copilot suggestion and don't know why
- Self-taught learners who accumulate patterns without deep understanding — and forget within days

---

## 2. Core Idea

**Thesis title: AI Tutor**

When a learner pastes AI-generated code they don't fully understand, CodeScope:

1. **Checks** it for common bug patterns (static analysis)
2. **Shows** exactly how it executes step-by-step with live variable states
3. **Explains** *why* it behaves that way in plain language
4. **Schedules** a brief review so they actually remember it

**Core framing:** Understand once. Verify it works. Remember it.

---

## 3. Thesis Contribution

This thesis presents an adaptive learning system that combines three proven techniques — **runtime tracing**, **LLM-generated explanation**, and **spaced repetition** — into a single coherent workflow.

The contribution is not any single component, but their **integration**: explanations grounded in actual variable state, and comprehension reinforced through systematic review.

> This thesis presents an AI tutor for AI-assisted coding — a system that grounds LLM-generated explanations in runtime variable state, and reinforces comprehension through spaced repetition.

---

## 4. System Architecture

```
[User pastes AI-generated Python code]
           ↓
Phase 0: Static Analysis
  → Scans for common AI bug patterns (free, unlimited)
           ↓
Phase 1: Execution Tracer
  → sys.settrace() + bytecode analysis
  → Step-by-step state capture (variables, branches, lines)
  → Side effects sandboxed (no imports, network, file ops)
           ↓
Phase 2: LLM Explanation Engine
  → GitHub Model (primary) / OpenAI (fallback)
  → Input: current line + actual variable state + branch context
  → Output: plain-language explanation grounded in real execution
           ↓
Phase 3: Spaced Repetition Review Queue
  → SM-2 scheduler
  → Saves trace + explanation as a "code fact"
  → Schedules review based on estimated difficulty
           ↓
Review Session (daily/weekly)
  → Shows code snippet + variable context
  → User recalls what it does
  → SM-2 updates interval based on response quality
```

---

## 5. Key Phases


| Phase       | Goal                              | What's Built                                                                     |
| ----------- | --------------------------------- | -------------------------------------------------------------------------------- |
| **Phase 0** | Immediate value on every paste    | Static analysis — 10 common AI bug patterns, inline annotations                  |
| **Phase 1** | Show how the code actually runs   | Execution tracer with sys.settrace(), step-by-step playback, branch highlighting |
| **Phase 2** | Explain *why* it behaves this way | LLM engine — execution-contextual prompts (line + state + branch)                |
| **Phase 3** | Make comprehension stick          | SM-2 spaced repetition review queue, daily review sessions                       |
| **Phase 4** | Turn into a learning system       | 20–30 hand-picked confusing AI-generated patterns with explanations              |


---

## 6. User Flows 

**Flow 1: Paste and Verify**

1. User pastes an AI-generated function they don't understand
2. Static analysis flags potential issues instantly
3. User clicks "See how it runs" → tracer animates each step
4. User sees: "At step 4, x = [1, 2] — the comprehension filtered everything out"
5. User understands → saves to review later

**Flow 2: Daily Review**

1. User opens CodeScope → sees "3 reviews due"
2. First card: code snippet traced 2 days ago
3. User recalls what it does, clicks "Good"
4. SM-2 schedules next review in 4 days
5. Done in ~2 minutes

---

## 7. Technical Stack


| Layer     | Technology                                |
| --------- | ----------------------------------------- |
| Frontend  | React + Vite + TypeScript                 |
| Backend   | FastAPI (Python)                          |
| Tracer    | `sys.settrace()` + bytecode analysis      |
| LLM       | Github Model (primary), OpenAI (fallback) |
| Database  | SQLite                                    |
| Streaming | Server-Sent Events (SSE)                  |


---

## 8. Evaluation Approach


| Metric                       | Method                                           |
| ---------------------------- | ------------------------------------------------ |
| Comprehension retention rate | 2-week follow-up on traced patterns              |
| Static analysis accuracy     | Synthetic benchmark, 50 snippets with known bugs |
| Review completion rate       | Track % of scheduled reviews done within 24h     |
| Time-to-understand           | Self-reported confidence before/after trace      |


---

## 9. What's In Scope (Thesis)

- Python only (thesis scope)
- Single-user web app (no team features)
- SQLite for data persistence
- End-to-end tracer + LLM + SR integration

## What's Out of Scope

- Multi-language support
- Mobile UI
- B2B/team features
- Formal IRB user study

---

## 10. Risks 

- **Users don't complete reviews** → Keep sessions under 2 minutes, explain the value of spacing upfront
- **Tracer blocks too much code** → Static analysis handles cases where sandboxing prevents execution

---

