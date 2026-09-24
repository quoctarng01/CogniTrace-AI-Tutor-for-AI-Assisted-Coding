# Thesis Abstract

## Title

**A State-Grounded AI Tutor for Personalized Programming Support Using Large Language Models**

## Status

Draft 2 — title aligned with formal submission (locked). Abstract and contributions reframed around the dual-axis "state" interpretation. Aligned with `docs/THESIS-01-STUDY-PROTOCOL.md`.

---

## Abstract (~280 words, thesis-grade)

Novice programmers increasingly rely on conversational AI assistants that hallucinate about *two* kinds of state: the runtime state of the student's code (what variables actually held at line 14) and the cognitive state of the learner (what this student actually misunderstands). The result is one-size-fits-all explanation: students copy-paste generated code without building the mental model of control flow that debugging requires.

This thesis investigates a **state-grounded AI tutor**: a system that conditions every AI response on two complementary state representations simultaneously — the runtime state of the program (captured by deterministic execution fingerprints: variables, branch outcomes, call frames) and the cognitive state of the learner (per-concept mastery from adaptive spaced repetition, misconception history, and a quantitative cognitive-load estimate). The system under study is CogniTrace, an integrated tutoring platform combining (1) retrieval-augmented generation over execution traces, (2) LLM-generated active-recall checkpoints at control-flow branches, (3) adaptive spaced repetition keyed to trace-derived concept tags, and (4) a learner-state channel that adapts prompt difficulty and review scheduling to per-student load and mastery.

We conduct a within-subjects study with N=24 first-year CS students comparing three conditions on a debugging-comprehension task battery: (a) Python Tutor alone, (b) Python Tutor plus ungrounded ChatGPT, and (c) CogniTrace. Primary outcomes are bug-identification accuracy and time-to-fix plus transfer-task accuracy on novel code. Secondary outcomes are one-week retention and subjective usability. The central hypothesis is that the dual-state-grounded condition improves transfer-task accuracy by at least 20 percentage points over the ungrounded condition (Cohen's d ≥ 0.6).

The contribution is twofold. **Empirically**, we provide one of the first controlled measurements of dual code-and-learner state grounding as a mechanism for reducing LLM hallucination in personalized programming support. **System-wise**, we document an integrated architecture that unifies runtime-state grounding and learner-state grounding in a single trace-aware workflow, with reusable design patterns for future AI tutoring systems.

---

## Keywords

AI tutoring, retrieval-augmented generation, grounded generation, active recall, spaced repetition, debugging comprehension, CS1, trace visualization, Python, LLM hallucination, learner modeling, cognitive load, adaptive difficulty, personalized programming support

---

## Research Questions

**RQ1 (primary):** Does state-grounded AI tutoring — conditioning every response on both runtime state and learner state — improve debugging comprehension in CS1 students compared to ungrounded LLM chat?

**RQ2 (secondary):** Does pairing LLM explanation with active-recall checkpoints at branch points produce additional improvement beyond passive observation of the explanation?

**RQ3 (secondary):** Does the system's per-concept adaptive review schedule improve one-week retention of debugging concepts compared to non-adaptive review?

RQ1 is the load-bearing question; RQ2 and RQ3 are exploratory and can be cut if N or timeline pressure requires it.

---

## Hypotheses

| ID | Hypothesis | Predicted effect | Measurement |
|---|---|---|---|
| H1 | Dual-state-grounded condition > ungrounded condition on transfer-task accuracy | ≥ +20 pp, Cohen's d ≥ 0.6 | Bug-identification accuracy on novel code |
| H2 | Adding active-recall checkpoints improves over grounded explanation alone | ≥ +10 pp additional | Transfer-task accuracy, condition C vs C' |
| H3 | Adaptive per-concept review > non-adaptive review on 1-week retention | ≥ +15 pp retention delta | Re-test accuracy after 7 days |

H1 is the pre-registered primary hypothesis. H2 and H3 are exploratory.

---

## Contributions (for thesis Chapter 1 and committee letter)

1. **Empirical.** A controlled within-subjects measurement isolating the contribution of *dual* state grounding (runtime + learner state) on debugging comprehension in personalized programming support — addressing a documented gap in the LLM-tutoring literature (most prior work uses conversational interfaces without runtime access, and none combine runtime and learner grounding in a single loop).

2. **Methodological.** Introduction of trace-content-addressed cache hit rate as a proxy for grounded-explanation reuse, validated against LLM hallucination counts in the runtime-state grounding case (RQ1 supporting analysis).

3. **System.** An integrated reference implementation of state-grounded LLM tutoring that fuses runtime-state grounding (RAG over execution traces) and learner-state grounding (cognitive-load estimation + SM-2 mastery + misconception history) into a single tutor loop, with active-recall checkpoint injection and concept-keyed spaced repetition.

4. **Pedagogical.** A custom SM-2 *soft-fail* modification (halving rather than resetting intervals on partial-credit responses) whose effect on retention can be evaluated against the standard SM-2 reset.

---

## Method Summary (one paragraph)

24 CS1 students complete a 5-minute baseline Python control-flow quiz, then work through three matched debugging tasks under three counterbalanced conditions (within-subjects, Latin square order). Each task requires identifying the location and cause of a planted bug, fixing it, and transferring the underlying concept to a novel program. Sessions are 75 minutes each. Outcomes: bug-identification accuracy, fix correctness, time-to-fix, transfer accuracy, pre/post quiz delta, and a 5-item usability survey. Optional 10-minute semi-structured interview for n=10 participants. Analysis: repeated-measures ANOVA across conditions, paired t-tests with Bonferroni correction for pairwise comparisons (A vs C, B vs C), Cohen's d for effect size.

Full protocol: `docs/THESIS-01-STUDY-PROTOCOL.md`.

---

## Thesis Structure (proposed 6-chapter format)

- **Chapter 1 — Introduction.** Research problem, motivation, research questions, hypotheses, contributions, thesis roadmap.
- **Chapter 2 — Background and Related Work.** LLM tutors (Khanmigo, ChatGPT, Copilot); program visualization (Python Tutor); grounded generation and hallucination in LLMs; active recall and spaced repetition in CS education.
- **Chapter 3 — System Design and Implementation.** CogniTrace architecture: trace-grounded RAG, active-recall checkpoints, adaptive SM-2. Engineering decisions and trade-offs.
- **Chapter 4 — Study Design.** Within-subjects protocol, participants, instruments, procedure, analysis plan, ethical considerations, pre-registration.
- **Chapter 5 — Results.** Descriptive statistics, ANOVA, pairwise comparisons, effect sizes, qualitative themes from interviews.
- **Chapter 6 — Discussion and Conclusion.** Interpretation, threats to validity, design recommendations for future trace-grounded AI tutors, future work.

---

## Why this title and abstract

The original working title "AI Tutor for Assisted Coding" describes a feature category, not a research contribution. The submitted title — **"A State-Grounded AI Tutor for Personalized Programming Support Using Large Language Models"** — is locked; it frames the contribution around **state grounding**, which in this thesis is interpreted along two complementary axes:

1. **Runtime state of the program** — execution frames, variables, branch outcomes, captured by deterministic execution fingerprints (formerly described as "trace grounding").
2. **Cognitive state of the learner** — per-concept mastery from SM-2, cognitive-load estimate, recent misconception history.

The submitted title intentionally uses the broader term "state-grounded" rather than "trace-grounded": the contribution is precisely the **unification** of runtime-state grounding with learner-state grounding in a single tutor loop, which is stronger than either axis in isolation. Chapter 1 introduces this dual-axis interpretation immediately after the title and the abstract restates it explicitly.

The abstract uses the standard four-paragraph thesis-abstract structure: (1) problem (both axes), (2) intervention (dual-axis grounding), (3) method, (4) contribution. Word count fits the 250-word limit common at most institutions.

---

## Versioning

| Version | Date | Change |
|---|---|---|
| 0.1 | Initial | "AI Tutor for Assisted Coding" |
| 1.0 | First draft | Research-question-first reframing, aligned to THESIS-01 protocol |
| 2.0 | This draft | Title aligned to submitted form ("A State-Grounded AI Tutor for Personalized Programming Support Using Large Language Models"); abstract and contributions reframed around dual-axis runtime-state + learner-state grounding |
