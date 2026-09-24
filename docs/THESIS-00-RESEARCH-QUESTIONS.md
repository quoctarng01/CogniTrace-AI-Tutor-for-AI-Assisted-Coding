# Research Questions, Hypotheses, and Pre-Registration

> Companion to [`THESIS-00-ABSTRACT.md`](./THESIS-00-ABSTRACT.md). Pulled from [`THESIS-01-STUDY-PROTOCOL.md`](./THESIS-01-STUDY-PROTOCOL.md) and aligned with the contribution claims in [`THESIS-02-CONTRIBUTIONS.md`](./THESIS-02-CONTRIBUTIONS.md).

---

## 1. Pre-Registered Hypothesis (H1)

**Statement.** Students who receive LLM explanations that are *grounded in the actual runtime trace* of their code will demonstrate higher transfer-task debugging accuracy than students who receive ungrounded LLM explanations of the same code.

**Operationalization.**

- Independent variable: explanation mode (grounded trace vs ungrounded).
- Dependent variable: bug-identification accuracy on a novel Python program that uses the same underlying concept (loops, conditionals, mutation) but with different names and structure.
- Effect-size threshold: Cohen's d ≥ 0.6, ≥ 20 percentage-point absolute improvement on transfer-task accuracy.
- Significance: α = 0.05 (two-sided), Bonferroni-adjusted for 3 pairwise comparisons.
- Sample size justification: With N=24 within-subjects and an expected large effect (d ≥ 0.6), power ≈ 0.85 using a paired t-test.

**Pre-registration.** This hypothesis is registered before data collection. The study protocol, instruments, and analysis plan are frozen as of the date recorded in `docs/THESIS-01-STUDY-PROTOCOL.md`. Any deviation from the pre-registered design is logged as a transparent deviation in the final report.

---

## 2. Exploratory Hypotheses (H2, H3)

### H2 — Active recall beyond explanation

**Statement.** Pairing grounded explanation with active-recall checkpoints at branch points will produce additional improvement beyond grounded explanation alone.

**Mechanism.** Karpicke & Roediger (2008) showed that active retrieval practice outperforms repeated passive study by a large margin in delayed retention. This hypothesis tests whether the *additional* cognitive effort of predicting the next state at a branch checkpoint translates to measurable transfer-task improvement.

**Operationalization.**

- Three-arm comparison: condition A (Python Tutor alone) vs condition C (CogniTrace with checkpoints) vs condition C' (CogniTrace without checkpoints, where the checkpoint UI is replaced by a passive "Continue" button).
- Predicted effect: ≥ 10 percentage-point additional improvement of C over C'.
- Status: exploratory. If N or timeline pressure forces dropping an arm, C vs C' is dropped first; A vs C (the H1 comparison) is preserved.

### H3 — Adaptive review retention

**Statement.** Adaptive per-concept review (where the SM-2 interval is keyed to the specific runtime concept a student missed, rather than the specific trace they missed) will improve one-week retention of debugging concepts compared to non-adaptive review.

**Operationalization.**

- Within-subjects: same students use CogniTrace in adaptive mode for half the concepts and non-adaptive mode for the other half.
- Predicted effect: ≥ 15 percentage-point retention delta on a 7-day post-test.
- Status: exploratory. This arm is the most expensive (requires a second visit from participants) and is the first to be cut under time pressure.

---

## 3. Research Questions

| ID | Question | Linked hypothesis | Priority |
|---|---|---|---|
| RQ1 | Does state-grounded AI tutoring (every response conditioned on both runtime state and learner state) improve debugging comprehension in CS1 students compared to ungrounded LLM chat? | H1 | Primary |
| RQ2 | Does pairing LLM explanation with active-recall checkpoints at branch points produce additional improvement beyond passive observation of the explanation? | H2 | Secondary |
| RQ3 | Does the system's per-concept adaptive review schedule improve one-week retention of debugging concepts compared to non-adaptive review? | H3 | Secondary |

**Load-bearing question.** RQ1 is the load-bearing contribution. RQ2 and RQ3 are exploratory and can be cut without invalidating the thesis. If the committee asks "what is the one question this thesis answers," the answer is RQ1.

---

## 4. Variables

### Independent variables

| Variable | Type | Levels | Source of variation |
|---|---|---|---|
| Explanation mode | within-subjects | (A) Python Tutor, (B) PT + ungrounded ChatGPT, (C) CogniTrace | Counterbalanced, Latin-square |
| Checkpoints | within-subjects | on (C), off (C') | Within-condition |
| Review adaptation | within-subjects | adaptive, non-adaptive | Within-concept |
| Order of conditions | within-subjects | 6 orderings | Latin square |

### Dependent variables

| Variable | Measurement | Reliability | Granularity |
|---|---|---|---|
| Bug-identification accuracy | % correct on a 6-bug battery | Inter-rater κ ≥ 0.8 | Per-task |
| Fix correctness | Binary per bug | n/a | Per-bug |
| Time-to-fix | Seconds from task reveal to fix save | Stopwatch | Per-task |
| Transfer accuracy | % correct on novel-code tasks with the same concept | Inter-rater κ ≥ 0.8 | Per-task |
| Pre/post quiz delta | 10-item quiz, both ends | Cronbach's α ≥ 0.7 | Per-student |
| SUS | 10-item System Usability Scale | Standard | Per-student |

### Mediating / control variables

- Prior programming experience (number of CS courses completed).
- Baseline Python control-flow quiz score.
- Time-on-task (measured via the existing analytics layer in `frontend/lib/analytics.ts`).

---

## 5. Analysis Plan

### Primary analysis (H1)

1. Within-subjects repeated-measures ANOVA across the three conditions.
2. Planned pairwise comparisons (paired t-tests, Bonferroni-corrected):
   - A vs C (RQ1 primary comparison).
   - B vs C (RQ1 contrast against ungrounded LLM control).
3. Effect size: Cohen's d for paired samples. Pre-registered threshold: d ≥ 0.6.
4. Report: mean ± SD per condition, F statistic, p value, d, and 95% CI on the difference.

### Secondary analyses

- H2: paired t-test on C vs C' for participants in both arms.
- H3: paired t-test on 7-day retention for adaptive vs non-adaptive concepts.

### Supporting analysis (cache hit rate as proxy for grounding reuse)

- Aggregate `llm_call_metrics.cache_hit` from the database (see `docs/MEASUREMENT.md`).
- Pre-registered expectation: cache hit rate ≥ 40% during the study. If hit rate is below this, log as a transparency note in the final report.

### Qualitative analysis

- 5-item Likert usability survey per session.
- Optional 10-minute semi-structured interview for n=10 (purposive sample: 3 high-improvement, 3 no-change, 3 low-improvement, 1 dropout).
- Thematic coding by two researchers; κ ≥ 0.7.

---

## 6. Threats to Validity

### Internal

- **Carryover effects.** Mitigation: counterbalanced order, ≥ 5-minute washout between conditions.
- **Practice effects on repeated task battery.** Mitigation: matched but not identical task pairs per condition; novel-code transfer tasks rule out memorization.
- **Experimenter bias.** Mitigation: automated scoring where possible; double-blind rubric for free-response items.

### External

- **Single institution.** Mitigation: report demographics; flag in discussion.
- **CS1 population only.** Not a threat to the thesis claim, but a limitation for generalization to CS2+.

### Construct

- **"Grounded" is operationalized via trace conditioning.** A reviewer might ask whether trace grounding is the active ingredient or whether the prompts alone improve quality. Mitigation: A/B the prompt across conditions to isolate the trace variable. This is registered as a transparency item in the analysis plan.

---

## 7. Pre-registration Record

| Field | Value |
|---|---|
| Pre-registration date | To be set when IRB approves. |
| Pre-registration URL | OSF or AsPredicted link, posted before data collection begins. |
| Deviations log | All deviations recorded in `docs/THESIS-DEVIATIONS.md` with date and rationale. |

---

## 8. Why These RQs Matter

A common committee question: "Why these three RQs instead of a single bigger one?" The answer is that RQ1 is the primary contribution; RQ2 isolates one cognitive ingredient (active recall) that could plausibly mediate the effect; RQ3 extends the finding from in-session to long-term retention. If RQ1 is significant but RQ2 is null, the contribution is more interesting (it says grounding works *even without* the active-recall ingredient), not less. If RQ1 is null and RQ2 is significant, the headline shifts — which is what the pre-registration is designed to handle honestly.
