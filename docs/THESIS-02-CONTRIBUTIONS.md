# Thesis Contributions

> Companion to [`THESIS-00-ABSTRACT.md`](./THESIS-00-ABSTRACT.md) and [`THESIS-00-RESEARCH-QUESTIONS.md`](./THESIS-00-RESEARCH-QUESTIONS.md). Each contribution is named, described, and tied to the system code or measurement that supports it.
>
> **Framing note (post-submission).** The submitted thesis title is "A State-Grounded AI Tutor for Personalized Programming Support Using Large Language Models." Throughout this document, "state-grounded" means *dual* state grounding: the runtime state of the program (variables, branch outcomes, call frames — captured by execution fingerprints) **and** the cognitive state of the learner (mastery, cognitive load, misconception history). The unification of these two state representations in a single tutor loop is the central conceptual contribution.

The thesis makes four named contributions. Each is independent of the others: a reviewer may accept or reject any one without affecting the rest. The system contribution is the engineering; the other three are research contributions.

---

## 1. Empirical Contribution

**Claim.** A controlled within-subjects measurement isolating the contribution of dual code-and-learner state grounding on debugging comprehension in personalized programming support, addressing a documented gap in the LLM-tutoring literature.

**Why it matters.** Most published work on LLM code tutoring uses conversational interfaces without runtime access to the student's code (e.g., prior evaluations of Khanmigo, ChatGPT in CS1 classrooms), and none that we are aware of condition simultaneously on learner cognitive state. When these systems are evaluated, the dependent variable is usually student satisfaction or task completion rate, not comprehension. This thesis contributes a controlled measurement of *comprehension* on a transfer task with **runtime-state grounding isolated as the primary independent variable** and **learner-state grounding (load-aware prompt difficulty, mastery-keyed review) layered on as the secondary independent variable**, allowing the dual grounding claim to be decomposed.

**Where it lives in the code.**

- The within-subjects protocol: [`THESIS-01-STUDY-PROTOCOL.md`](./THESIS-01-STUDY-PROTOCOL.md).
- The pre-registered hypothesis H1: [`THESIS-00-RESEARCH-QUESTIONS.md`](./THESIS-00-RESEARCH-QUESTIONS.md#1-pre-registered-hypothesis-h1).
- The matched task battery: `docs/study-instruments/task-battery-v1.md` (to be drafted before data collection).
- The pre-registration record: [`THESIS-00-RESEARCH-QUESTIONS.md`](./THESIS-00-RESEARCH-QUESTIONS.md#7-pre-registration-record).

**Evidence the committee will ask for.** Raw data file, analysis script, and a reproducibility appendix in the thesis. Two raters with inter-rater κ ≥ 0.8 on the comprehension rubric. Pre-registered analysis pipeline that runs without modification on the raw data. A decomposition analysis isolating the runtime-state and learner-state contributions.

---

## 2. Methodological Contribution

**Claim.** Introduction of *trace-content-addressed cache hit rate* as a proxy for runtime-state-grounded explanation reuse, validated against LLM hallucination counts in the runtime-state grounding case (RQ1 supporting analysis).

**Why it matters.** Cache hit rate on the `(code, line_number, variable_state)` key directly measures how often the same runtime frame recurs across students — which is the operationalization of runtime-state grounding reuse. If the cache hit rate is high and the hallucination rate (manually labelled on a N=50 sample of cached explanations) is low, this validates cache hit rate as a low-cost monitoring metric for any future state-grounded tutoring system. This is a small but defensible methodological contribution in its own right.

**Where it lives in the code.**

- The cache key construction: [`backend/app/services/llm_router.py`](../../backend/app/services/llm_router.py) — `make_cache_key()` function. SHA-256 over `(code[:200], line_number, line_content[:50], sha256(locals_dict))`.
- The cache hit/miss logging: `llm_call_metrics.cache_hit` in [`backend/migrations/V011__llm_call_metrics.sql`](../../backend/migrations/V011__llm_call_metrics.sql) (added by Workstream 4).
- The cache hit rate endpoint: `GET /api/metrics/cache-hit-rate?window=7d` (added by Workstream 10).

**Evidence the committee will ask for.** A scatter plot of cache hit rate vs hallucination count per trace category. Pearson r and a Bonferroni-corrected significance test. Expected: negative correlation with r ≥ -0.5. If r is small, the methodological claim is weaker but the empirical claim survives.

---

## 3. System Contribution

**Claim.** An integrated reference implementation of *dual* state-grounded LLM tutoring — every LLM prompt is conditioned on both the runtime-state fingerprint and the learner-state profile (mastery + load + misconception history) — with active-recall checkpoint injection and concept-keyed spaced repetition, and reusable design patterns.

**Why it matters.** Each of the components — RAG over traces, learner-model-driven adaptive difficulty, active-recall checkpoint UI, adaptive SM-2 — exists in prior work in isolation. What is new is putting them into a single trace-aware workflow in which **runtime-state and learner-state grounding share a content-addressed cache and a unified prompt construction** (T1-A + T1-C + T1-D combined loop). Future AI tutoring systems can copy this architecture without re-deriving it. The thesis contributes not just the components but their *unification under one state-grounded loop*.

**Where it lives in the code.**

- Runtime-state grounding (the RAG layer): [`backend/app/services/llm_router.py`](../../backend/app/services/llm_router.py) — `SYSTEM_PROMPT` and `USER_PROMPT_TEMPLATE` make the runtime-frame conditioning explicit.
- Learner-state grounding (load + mastery channel): `backend/app/services/load_estimator.py` — cognitive-load estimator, integrated into the `diagnose_checkpoint_error` endpoint and the `/api/load/trace` endpoint (T1-A).
- Learner-state history in tutor prompts: `backend/app/services/checkpoint_selector.py` and the misconception-history channel used inside `diagnose_misconception` in [`backend/app/routers/llm.py`](../../backend/app/routers/llm.py) (T1-C).
- Checkpoint injection: [`backend/tracer/tracer.py`](../../backend/tracer/tracer.py) — `generate_tutor_checkpoints()` and [`backend/app/routers/llm.py`](../../backend/app/routers/llm.py) — `DiagnoseRequest` / `diagnose_checkpoint_error()`.
- Adaptive SM-2: [`frontend/lib/sm2.ts`](../../frontend/lib/sm2.ts) — `sm2()` function plus the *soft-fail* modification (halving rather than resetting on a Hard rating).
- Full data flow: [`ARCHITECTURE.md`](./ARCHITECTURE.md).

**Evidence the committee will ask for.** The architecture diagram in [`ARCHITECTURE.md`](./ARCHITECTURE.md), the unit tests covering each component (28 unit test files, see [`backend/tests/unit/`](../../backend/tests/unit/)), and the integration tests covering the end-to-end flow (6 integration test files in [`backend/tests/integration/`](../../backend/tests/integration/)).

---

## 4. Pedagogical Contribution

**Claim.** A custom SM-2 *soft-fail* modification whose effect on retention can be evaluated against the standard SM-2 reset. Specifically, on a `Hard` rating the interval and repetition count are halved rather than reset to 1 / 0; this keeps the card in the active review pool without the catastrophic interval collapse that causes student frustration and dropout.

**Why it matters.** Standard SM-2 resets the interval to 1 day on a failed recall. In practice, this causes students to feel they have "lost progress" on a card they partially understood, which is a known dropout trigger in spaced-repetition platforms (Wozniak, 1990; Ebbinghaus's original observation). The soft-fail modification is a small change with a defensible theoretical motivation and a testable retention effect (H3).

**Where it lives in the code.**

- The standard SM-2 reset behaviour: [`frontend/lib/sm2.ts`](../../frontend/lib/sm2.ts) — the `q < 3` branch (the file currently implements the standard reset; the soft-fail is a one-line change in that branch).
- The soft-fail modification is staged in [`backend/lib/sm2_soft_fail.py`](../../backend/lib/sm2_soft_fail.py) (added by Workstream 6) so the A/B comparison is one conditional away.
- The H3 measurement protocol: [`THESIS-00-RESEARCH-QUESTIONS.md`](./THESIS-00-RESEARCH-QUESTIONS.md#h3--adaptive-review-retention).

**Evidence the committee will ask for.** Within-subjects retention delta (adaptive mode vs non-adaptive mode) at 7 days post-test. Threshold: ≥ +15 pp retention delta. Pre-registered.

---

## 5. How These Contributions Map to Thesis Chapters

| Chapter | Contributions featured |
|---|---|
| Chapter 1 — Introduction | All four (overview). |
| Chapter 2 — Background | Citations supporting each (Karpicke & Roediger 2008 for active recall; Wozniak 1990 for SM-2; recent LLM-hallucination literature for grounding). |
| Chapter 3 — System Design | System (3) only. Engineering trade-offs. |
| Chapter 4 — Study Design | Methodological (2) design + Empirical (1) protocol. |
| Chapter 5 — Results | Empirical (1) primary, plus Methodological (2) supporting. |
| Chapter 6 — Discussion | Pedagogical (4) interpretation, threats to validity, future work. |

---

## 6. Reviewer-Proofing

Each contribution is structured so a reviewer can evaluate it on its own:

- **Empirical (1)** is the easiest to attack. The pre-registration is the shield. If H1 holds with d ≥ 0.6, the contribution stands.
- **Methodological (2)** is the easiest to undervalue. If the cache hit / hallucination correlation is not significant, this contribution is partially conceded but does not block the others.
- **System (3)** is the easiest to accept. The code is open. A reviewer can run it.
- **Pedagogical (4)** is the most defensible against novelty attacks because it is a one-line behavioural change with a clear theoretical motivation. The empirical effect (H3) is optional; the contribution stands on the design rationale alone.

This structure is intentional. A thesis that depends on every contribution surviving review is fragile. A thesis that survives even if one or two contributions are conceded is robust.
