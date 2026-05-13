# CodeScope Analysis — Product Research

**Status:** Final
**Version:** 4.0 (post-study-remove)
**Date:** 2026-04-30
**Based on:** research_report.md, diffdoctor_review.md, and conversation analysis
**Note:** This is NOT a research study design. Formal study materials (telemetry pipeline, evaluation pipeline, participant recruitment, statistical analysis) have been removed. See ARCHITECTURE.md for technical architecture.

---

## 1. The Problem

AI coding assistants (GitHub Copilot, Cursor, Claude Code) have achieved widespread adoption. Yet a significant proportion of AI tool users report:

- **Copying suggestions without fully reviewing the code** (46%, GitHub Copilot Survey 2023)
- **Spending more time debugging AI-generated code than writing it manually** (41%, Stack Overflow 2024)
- **Being unable to explain their own code** when asked by a team lead or during an interview

The "AI code comprehension gap" — the gap between what developers can generate with AI and what they can understand — is now a mainstream developer experience.

**Why does this happen?** Cognitive load theory (Sweller 1988) predicts that mismatches between code structure and mental models cause cognitive overload. AI-generated code systematically differs from textbook code: it contains more complex control flow, over-engineering patterns, non-idiomatic API usage, and implicit assumptions about types and state. These differences are not visible from reading the code — but they become visible when the code runs.

---

## 2. Target Users

### Primary: Priya (Student Developer)

**Profile:** Final-year CS student, 23, using GitHub Copilot to complete a final project.

**Pain:** 60–80% of her code is AI-generated. She can run it, but when something breaks she doesn't know where to look. She can't debug what she didn't write. She can't ask for help because she can't explain what she built.

**Fear:** Shipping broken code because she couldn't understand what she deployed.

**Context:** Likely working from a laptop. No local GPU. Desktop environment. Comfortable with Python. Needs zero-setup tools — she won't install Ollama or configure a local LLM. CodeScope uses Ollama Cloud by default, so she gets explanations with no setup.

**How CodeScope helps:** She pastes a function, watches it execute, and suddenly understands the nested comprehension that was generating her bug. The visualization closes the gap that reading alone cannot.

> **Note for technically capable users (e.g., Marcus):** Users who want full privacy can switch to local Ollama (`localhost:11434`) in their profile settings. This is an optional override — the default requires zero setup.

---

### Secondary: Marcus (Junior Developer)

**Profile:** Junior developer at a 15-person startup, 28, uses Cursor daily.

**Pain:** His team lead asked him to explain a feature he shipped last week. He couldn't.

**Fear:** Being exposed as not actually knowing how to code.

**Context:** More technically capable than Priya. May have local Ollama running. Values sharing and collaboration. Cares about streaks and gamification.

**How CodeScope helps:** He steps backward through the trace of the code he shipped, sees the implicit None check he didn't write, and finally understands exactly what his code does and why.

---

## 3. Competitive Landscape


| Tool                           | What it does                                | Why CodeScope is different                                                                                                                                |
| ------------------------------ | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python Tutor (pythontutor.com) | Step-by-step Python execution visualization | Python Tutor is designed for textbook code; CodeScope is designed for AI-generated code with pattern detection, "why" explanations, and spaced repetition |
| GitHub Copilot                 | Code generation                             | CodeScope is the opposite: a comprehension tool, not a generation tool                                                                                    |
| Cursor / Claude Code           | AI chat about code                          | These tools explain code in the abstract; CodeScope explains code in the context of its actual execution state                                            |
| Jeliot / TRAKLA2               | Academic code visualization                 | Designed for CS education, not AI code comprehension; no LLM integration                                                                                  |


**CodeScope's differentiation:** No other tool combines (1) bytecode-level trace visualization, (2) execution-contextual "why" explanations via LLM, and (3) spaced repetition review — purpose-built for the AI code comprehension problem.

---

## 4. Key Insights

### Insight 1: Reading code ≠ understanding code

A developer can read a nested list comprehension and understand its syntax. But understanding why `if not x` works differently from `if x is None` — in the context of the actual values flowing through it — requires watching it execute. This is the "Aha!" moment CodeScope is designed to create.

### Insight 2: The "why" must be grounded in execution state

Generic "this is a list comprehension" explanations are not useful. Priya doesn't need to know what a list comprehension is in general — she needs to know why this specific list comprehension, with these specific inputs, produces this specific output at this specific line. CodeScope's "why" prompt includes the current variable state, which grounds the explanation in execution reality.

### Insight 3: Understanding must be retained, not just experienced

An "Aha!" moment fades. Without spaced repetition, Priya will forget the insight within a week. The review queue transforms a one-time experience into durable learning.

### Insight 4: The free tier is the funnel

Priya won't pay before she trusts the product. 50 free traces/month is enough to build a habit. The Pro conversion happens when the free tier has already demonstrated value.

---

## 5. Freemium Economics


| Tier | Price     | Revenue model                                                                               |
| ---- | --------- | ------------------------------------------------------------------------------------------- |
| Free | $0        | 50 traces/month (soft limit; prompts upgrade; not server-blocked) + 20 "why" questions/hour |
| Pro  | $15/month | Unlimited traces + unlimited "why" + review queue + sharing                                 |


> **Note on free-tier limits:** The 50 traces/month is a soft limit enforced in localStorage — users are prompted to upgrade but not blocked from tracing. The "why" rate limit (20/hour) is a hard limit enforced server-side to protect Ollama Cloud from abuse. These are different mechanisms serving different purposes.

**Break-even:** At $15/month and 2.9% + $0.30/transaction, break-even is at $0.97/revenue per paying user. At 500 free users with 2% conversion = 10 paying users = $150/month. Sufficient for solo operation (Railway backend hosting).

> **Assumption note:** The 2% conversion rate is a target benchmark, not a validated metric. This is a typical range for freemium SaaS tools (Duolingo, Notion, etc. report 1–4% conversion). The PRD sets ≥ 2% as a lagging indicator target. If 30-day free-tier retention is ≥ 40% but conversion is < 2%, investigate whether the upgrade prompt is too aggressive or the Pro value proposition is unclear.

---

## 6. Risk Assessment


| Risk                                      | Likelihood | Impact | Mitigation                                                                               |
| ----------------------------------------- | ---------- | ------ | ---------------------------------------------------------------------------------------- |
| Ollama Cloud goes down or rate-limits     | Medium     | High   | Claude API fallback always available                                                     |
| Claude API costs exceed $5 free tier      | Low        | Medium | Token bucket rate limiting (Redis-backed for multi-instance); monitor usage              |
| Tracer overhead > 200ms (SPIKE 1)         | Medium     | Low    | Move to async thread pool; no architecture change needed                                 |
| No Pro conversions                        | Medium     | High   | Focus on onboarding UX; 30-day check on free-tier retention                              |
| Redis unavailable (multi-instance bypass) | Medium     | Medium | In-memory fallback with explicit warning log; Redis required for distributed correctness |
| Users paste malicious code                | Low        | High   | Side-effect detection blocks dangerous patterns; subprocess sandbox limits resources     |
| Supabase free tier exceeded               | Low        | Low    | Upgrade to paid tier; tracer works without persistence                                   |
| CS students not English-native            | Medium     | Low    | i18n support (EN + VI in v1); Accept-Language header auto-detection                      |


---

## Appendix: What Changed from v3.0 (Study Design)


| Removed                                                  | Reason                                                               |
| -------------------------------------------------------- | -------------------------------------------------------------------- |
| TelemetryEvent + TelemetrySession tables                 | No formal research study                                             |
| REQ-STUDY-01 through REQ-STUDY-04                        | Study mode, consent, demographics, comprehension quiz — out of scope |
| Latin Square counterbalancing                            | Research design element — not applicable to product                  |
| Statistical analysis plan (Wilcoxon, Bayes factors)      | Research methodology — not applicable to product                     |
| OSF pre-registration                                     | Research infrastructure — not applicable to product                  |
| NASA-TLX cognitive load measurement                      | Research instrument — not applicable to product                      |
| Interaction telemetry (pause duration, step-back events) | Research data collection — not applicable to product                 |
| Thematic analysis (Braun & Clarke)                       | Research method — not applicable to product                          |
| participantId, sessionId, experience_level fields        | Research tracking — not applicable to product                        |



| Retained                      | Reason                                           |
| ----------------------------- | ------------------------------------------------ |
| User personas (Priya, Marcus) | Product design foundation                        |
| Competitive landscape         | Validates product differentiation                |
| Freemium economics            | Revenue model still applies                      |
| Risk assessment               | Valid for product deployment                     |
| Key insights                  | Derived from problem research, valid for product |
