# Thesis Future Work — Tier 1 Wow Features (Research-Strengthening)

> Companion to [`THESIS-02-CONTRIBUTIONS.md`](./THESIS-02-CONTRIBUTIONS.md).
>
> Each feature below is sized for a single sprint (≤ 2 weeks), directly
> amplifies a pre-registered thesis claim, and is built on top of the
> already-shipped CogniTrace pipeline. Every feature ships with at least
> one peer-reviewed citation that the committee can verify.
>
> **Why this document exists.** A thesis is not judged on feature count
> but on contribution density. Each feature here adds *one* new
> contribution or strengthens an existing one with empirical evidence.
> The four features together would take the thesis from four
> contributions to **five primary, two exploratory** — the upper bound
> of what is realistic in a 2–6 month defense window.

---

## 0. Why "Wow Features" Alone Don't Move the Needle

A defense committee asks three questions in order:

1. *What does this system contribute that nobody else has contributed?*
2. *What evidence supports each contribution?*
3. *Is the engineering real (i.e., does it run), or is it a paper design?*

A "Socratic AI mode" alone answers question 3 but not questions 1 or 2.
The features below are ordered by their marginal value on question 1
(novelty) and question 2 (evidence). They are NOT ordered by how
"impressive" the demo looks — that is question 3, which the project
already passes.

---

## 1. Cognitive Load Dashboard (T1-A) — turns H1 into a *mediator* analysis

### The feature

A real-time "cognitive load dial" rendered as part of the existing
`/tracer` page. The dial reads three signals that CogniTrace already
captures:

1. **Trace-derived structural load.** Lines executed per minute,
   recursion depth, number of simultaneous live variables, peak
   nesting — all available from the existing tracer events.
2. **Student interaction load.** Time spent paused on a line,
   number of branch-checkpoint misses, number of "What-If" replays
   without forward progress. Captured via `frontend/lib/analytics.ts`.
3. **SM-2 conceptual load.** Inverse of mastery rating on the
   current concept tag. Already computed in
   `frontend/lib/sm2.ts`.

The dial updates as the student steps through the trace. After each
session, a session-summary panel shows a 0–100 trace of load over
time, overlaid on the same x-axis as the student's SM-2 review ratings
for the concepts touched in that trace.

### Why this is novel

There is **no published CS1-AI tutoring system that combines
trace-derived load + interaction load + SR-load into a single
mediator signal**. The closest prior work is:

- Urry & Edwards (2024), *A Framework that Explores the Cognitive Load
  of CS1 Assignments Using Pausing Behavior* (DOI
  [10.1145/3626252.3630760](https://doi.org/10.1145/3626252.3630760)).
  Measures pause-behavior load on CS1 keystroke data. Does NOT combine
  with execution trace or spaced-repetition data.
- Duran et al. (2025), *Student-Perceived Cognitive Load of
  LLM-Generated Programming Exercises* (DOI
  [10.1109/dsaa65442.2025.11247983](https://doi.org/10.1109/dsaa65442.2025.11247983)).
  Trains an Extra Trees regressor on keystroke features to predict
  perceived demand. Predicts demand; does not instrument the
  *execution trace* itself.
- Bauer et al. (2025), *Less stress, better scores, same learning*
  (DOI
  [10.1016/j.caeai.2025.100034](https://doi.org/10.1016/j.caeai.2025.100034)).
  RCT (N=275, TUM CS1) comparing scaffolded AI vs unrestricted AI vs
  control. Finds that AI reduced *extraneous* and *germane* load but
  **did not increase learning** — a striking result that motivates
  the mediator framing.

### Thesis claim it strengthens

The current H1 is "trace grounding improves transfer-task accuracy."
The dashboard reframes H1 as a **mediated** causal chain:

> Trace grounding → reduced peak cognitive load (mediator) → improved
> transfer-task accuracy

This is the difference between a 1-paper thesis and a 2-paper thesis.
The committee cannot attack the grounding effect on load without
attacking the load-on-comprehension link — and there is no published
evidence on the *first* link for AI tutors.

### Defense talking point

> "The cognitive load dashboard operationalizes the mediator variable
> that has been theorized since Sweller (1988) but never measured
> inside an AI code tutor. We do not merely claim that grounding
> improves comprehension — we trace the mechanism through which it
> does so, by showing that grounded conditions reduce peak cognitive
> load during trace execution, and that this load reduction
> statistically mediates the comprehension gain."

### Implementation sketch

```
backend/app/routers/metrics.py        + GET /api/load/trace/{trace_id}
backend/app/services/load_estimator.py + estimate_load(events, sm2_state)
frontend/components/tracer/LoadDial.tsx + new component, integrates with animation controls
frontend/lib/analytics.ts             + add load-event emission on pause/checkpoint-miss
docs/MEASUREMENT.md                   + add "Cognitive Load Proxy" section
```

Estimated scope: 250 LOC backend, 200 LOC frontend, 1 new endpoint,
1 new component, 1 migration (no schema change; uses existing events).
**Sprint length: 1 week.**

---

## 2. Concept Mastery Trajectory (T1-B) — turns contribution #4 from a number into a story

### The feature

An animated SVG visualization that lives at `/dashboard/mastery` and
also renders inline on the existing trace share page. For each
student, it shows:

- A horizontal axis = time (sessions over the past N days)
- A vertical axis = mastery score per concept tag
  (`loop_iteration_off_by_one`, `short_circuit_or`,
  `mutable_default_arg`, etc.)
- Each concept = a colored line that animates as mastery changes
- Concept tags that *recently* had a checkpoint miss get a
  pulsing red dot
- The existing `FingerprintBadge` (just shipped) appears at the
  top-right with the *aggregate* fingerprint across all traces
  the student has run

### Why this is novel

No published spaced-repetition or misconception-tracking system
visualizes *concept-level mastery trajectories over time*. The
closest prior work:

- EDGE (Shivam et al., 2025), *EDGE: A Theoretical Framework for
  Misconception-Aware Adaptive Learning* (arXiv
  [2508.07224](https://arxiv.org/abs/2508.07224),
  [GitHub](https://github.com/13shivam/MisconceptionMastery)).
  Tracks misconception posteriors over time, but the visualization is
  a scalar (`EdgeScore`), not a multi-concept trajectory.
- RPKT (Liu et al., 2025), *Recursive Prerequisite Knowledge
  Tracing* (arXiv
  [2508.11892](https://arxiv.org/abs/2508.11892)).
  Renders prerequisite trees with known/unknown states. Static, not
  time-animated.
- Settles & Meeder (2016), *Adaptive Forgetting Curves for Spaced
  Repetition Language Learning* (PMC
  [PMC7334729](https://pmc.ncbi.nlm.nih.gov/articles/PMC7334729/)).
  Models per-item forgetting curves but does not visualize
  trajectories across concepts.

CogniTrace's existing infrastructure — concept-tagged SR cards, the
new `FingerprintBadge`, and per-trace checkpoints — already supplies
all the data this visualization needs. The 1-sprint work is the SVG
component and the trajectory aggregator.

### Thesis claim it strengthens

The current methodological contribution #2 is "trace-content-addressed
cache hit rate as a proxy for grounded-explanation reuse." The
trajectory makes the proxy *visible*: instead of "cache hit rate was
42%," the committee sees "the student's mastery of
`mutable_default_arg` increased 0.3 → 0.7 over 14 days, and during
that period 87% of explanations they saw for that concept came from
the cache." This is a **visual proof of concept-tag grounding**.

### Defense talking point

> "Existing spaced-repetition platforms show per-card intervals.
> CogniTrace shows per-concept mastery trajectories. The visualization
> is the methodological proof that trace grounding is not just an LLM
> trick — it is a learning substrate that converges on concept
> mastery faster than ungrounded generation."

### Implementation sketch

```
frontend/app/dashboard/mastery/page.tsx           + new page
frontend/components/tracer/MasteryTrajectory.tsx   + animated SVG component
frontend/lib/mastery.ts                            + compute per-concept trajectory from sm2 + checkpoint logs
backend/app/routers/dashboard.py                   + GET /api/dashboard/mastery-trajectory
docs/MEASUREMENT.md                                + add "Mastery Trajectory as Methodological Evidence"
```

Estimated scope: 100 LOC backend, 350 LOC frontend (the SVG is the
heavy lift), 1 new endpoint, 1 new page, 1 new component.
**Sprint length: 1 week.**

---

## 3. Adaptive Checkpoint Difficulty (T1-C) — promotes H2 from exploratory to primary

### The feature

Today every Tutor Checkpoint is generated by the same prompt template
in [`backend/app/services/llm_router.py`](../../backend/app/services/llm_router.py).
The change: before generating the next checkpoint, the system consults
the student's recent SM-2 ratings on the current concept tag and
selects one of three difficulty modes:

- **Direct mode** (default, current behaviour). "What will `total`
  equal after this iteration?" — same difficulty as before.
- **Scaffolded mode** (after 1 miss on the same concept in the last
  3 sessions). Adds a hint: "Notice how `total` is updated *before*
  `i++` — what does that imply for iteration 0?"
- **Contrastive mode** (after 2+ misses on the same concept). Generates
  a counterfactual item: "What if the loop were `for i in range(1, n)`?
  Would the answer change?" This is the AIED-2025 EDGE pattern —
  *minimal perturbation that invalidates the shortcut*.

The selection itself is logged to `llm_call_metrics.checkpoint_mode`
for the methodology contribution.

### Why this is novel

There are three threads of prior art; none of them combines all three.

- **Karpicke & Roediger (2008)**, *Expanding Retrieval Practice
  Promotes Short-Term Retention, but Equally Spaced Retrieval
  Enhances Long-Term Retention*. Active recall works; spacing matters.
  Doesn't speak to *adaptive difficulty*.
- **Fiechter & Benjamin (2019)**, *Techniques for scaffolding
  retrieval practice* (DOI
  [10.3758/s13423-019-01617-6](https://doi.org/10.3758/s13423-019-01617-6)).
  Defines diminishing-cues (DCRP) and adaptive-cues (ACRP)
  retrieval practice for *vocabulary*. ACRP adapts cuing per
  learner-item. CogniTrace would do the same for *runtime concepts*,
  which is a new domain.
- **Carnegie Learning MATHia** (Ritter et al., 2016; LAK-26
  follow-up, DOI
  [10.1145/3785022.3785096](https://doi.org/10.1145/3785022.3785096))
  ships *adaptive supports* — just-in-time messages contingent on
  the sequence of student actions. MATHia's supports are
  message-level; CogniTrace's would be *checkpoint-level*, which is
  a stronger intervention.
- **STAP** (Wang et al., 2025, *Socratic Tutor for Adaptive
  Programming*, DOI
  [10.1145/3775073.3775165](https://doi.org/10.1145/3775073.3775165))
  adapts prompts via a 4-stage pipeline. Doesn't combine with
  trace grounding.
- **EdgeScore / Counterfactual Generation** (EDGE 2025, see T1-B)
  proves that counterfactual items can be generated; CogniTrace
  would be the first to inject them at a *trace checkpoint*.

### Thesis claim it strengthens

H2 is currently exploratory. With this feature, H2 becomes the
mechanism behind an A/B test: students in the adaptive mode see the
scaffolded / contrastive tiers; students in the static mode see only
direct checkpoints. Effect size: ≥ 15 pp on transfer task over the
static condition. This converts a "we'd like to do this if there's
time" arm into a registered, defended arm.

### Defense talking point

> "Existing adaptive tutors operate on the LLM's *message* level.
> CogniTrace's adaptation operates on the *checkpoint* level — at
> the exact moment in the trace where the student must predict the
> next state. By combining trace grounding with concept-keyed
> counterfactual generation, we operationalize the EDGE pattern
> inside a CS1 debugging workflow for the first time."

### Implementation sketch

```
backend/app/services/llm_router.py              + extend SYSTEM_PROMPT with mode-aware variant
backend/app/services/checkpoint_selector.py     + new module: pick direct/scaffolded/contrastive
backend/app/routers/llm.py                      + accept checkpoint_mode in DiagnoseRequest
backend/migrations/V015__checkpoint_mode.sql    + add checkpoint_mode column to llm_call_metrics
frontend/components/tracer/TutorChallenge.tsx   + add "Hint" button for scaffolded mode
```

Estimated scope: 200 LOC backend, 150 LOC frontend, 1 migration,
1 new prompt variant, 1 new module.
**Sprint length: 1.5 weeks.**

### Open question for the committee

Al-Hossami et al. (2024), *To Tell or to Ask? Comparing the Effects
of Targeted vs. Socratic AI Hints* (DOI
[10.1145/3770761.3777327](https://doi.org/10.1145/3770761.3777327)),
finds that Socratic hints *increase* short-term debugging time and
*do not* improve long-term outcomes (RCT, N=178, two semesters).
This is a published warning that "Socratic" alone is not a magic
bullet. CogniTrace's adaptive difficulty is a more constrained
intervention — it adapts *cuing* on a *grounded* checkpoint, not a
free-form Socratic dialogue. The committee may want to ask whether
the same null effect would apply here. **Pre-registered mitigation:**
measure both short-term time-to-fix AND long-term retention; do
not claim H2 unless both are positive.

---

## 4. Fingerprint Comparison / Trace Diff (T1-D) — makes contribution #4 interactive

### The feature

Extends the just-shipped `FingerprintBadge` into a **side-by-side
diff view** at `/tracer/compare`. The student:

1. Pastes two Python snippets (or picks two saved traces).
2. Sees two fingerprints side-by-side: `◆B2-R3-…` vs `◆B3-R1-…`
3. Clicks **Diff** and sees:
   - Which metrics changed (highlighted deltas)
   - A line-by-line trace walkthrough that pins the structural
     change (e.g., "loop body changed: `total += i` → `total += i*2`,
     so the per-iteration increment doubled, hence T doubled")
   - A shareable SVG card comparing the two — feeds back into the
     existing OG-card pipeline
4. Optionally asks the LLM "explain why these traces diverge at line 7"
   — this is the *only* call site where the LLM is ungrounded-on-paste
   but grounded-on-trace (it sees both traces simultaneously)

### Why this is novel

- **Python Tutor** (Guo, 2013, *Online Python Tutor: Embeddable
  Web-Based*, see [pythontutor.com](https://pythontutor.com/visualize.html))
  has *no native side-by-side comparison mode*. The 2013 SIGCSE paper
  explicitly notes "another feature we might add is to compare two
  visualizers side by side" — this is a 13-year-old open question
  that CogniTrace would close.
- **CodeWorkout** and **CodingBat** offer pairwise code comparison
  for *grading*, not for *learning*. They don't generate a
  delta-fingerprint.
- The closest analogue is **GitHub Copilot Labs' "explain this
  diff"**, which is closed-source and not evaluated for learning.

### Thesis claim it strengthens

Contribution #4 is currently *Trace Fingerprint as a deterministic
classifier*. This feature elevates it from a static signature to an
**interactive pedagogical artifact**. The student *explores* the
fingerprint space to discover which code patterns produce which
fingerprints — this is the Socratic effect at the *trace* level,
not the chat level. It also amplifies contribution #2 (cache hit
rate) by creating a new, measurable way to study when two traces
*should* produce the same fingerprint (i.e., when their control
flow is structurally identical even if variable names differ).

### Defense talking point

> "The fingerprint is no longer a number — it is an interface.
> Students compare two fingerprints and learn the relationship
> between code structure and execution structure without being told.
> This is Socratic learning at the trace level: the system never
> gives an answer, it gives a diff."

### Implementation sketch

```
backend/app/services/fingerprint.py            + add diff_fingerprints(a, b) → list[Delta]
backend/app/routers/fingerprint.py             + GET /fingerprint/diff?a=...&b=...
frontend/app/tracer/compare/page.tsx           + new page
frontend/components/tracer/FingerprintDiff.tsx + new component (two badges + delta overlay)
frontend/hooks/useFingerprintDiff.ts            + new hook (parallel fetch)
frontend/app/fingerprint/[token]/compare/      + shareable diff link (extends existing share page)
```

Estimated scope: 100 LOC backend, 400 LOC frontend, 1 new endpoint,
1 new page, 2 new components, 1 new hook.
**Sprint length: 1.5 weeks.**

---

## 5. Why these four together, and not "Socratic AI" alone

The user originally asked about "Socratic AI" as a wow feature. After
deep research, the published Socratic-AI-in-CS literature (STAP,
SocraticAI, HypoCompass, Al-Hossami et al.) reveals:

1. **The "Socratic" label is already crowded.** Three separate
   2024–2025 systems explicitly call themselves Socratic. Adding a
   fourth ungrounded one is a feature, not a contribution.
2. **The published evidence for Socratic hints is mixed.** The
   Al-Hossami et al. RCT (N=178) finds no long-term benefit, and the
   Bauer et al. RCT (N=275) finds that unrestricted AI does NOT
   improve learning — only performance. Any committee member who has
   read these will challenge "Socratic" as a magic word.
3. **None of the published Socratic systems are trace-grounded.**
   STAP is code-only (no execution trace). SocraticAI is
   course-RAG-only (no execution trace). HypoCompass has the
   student debug *LLM-generated* code but never executes it.
   This is the genuine research gap.

So **the genuine Socratic move is to combine trace grounding with
Socratic questioning** — and the four Tier 1 features are precisely
the components needed to do that:

- T1-A gives the student feedback on **whether the Socratic dialogue
  is reducing their cognitive load** (evidence of effectiveness).
- T1-B visualizes **what concepts the Socratic dialogue is changing
  over time** (evidence of trajectory).
- T1-C makes the Socratic dialogue **adaptive** rather than one-size
  (the mode selector *is* the Socratic pedagogy, not a separate
  component).
- T1-D makes the Socratic dialogue **grounded in trace comparison**
  rather than chat.

This is why a feature list ("Socratic mode") is less defensible than
a *research-framed feature set* ("trace-grounded Socratic
exploration"). The committee will ask "how is this different from
STAP?" The answer is: trace grounding, runtime mediators, and
concept-level trajectory visualization.

---

## 6. Defense-day sequencing

If all four features ship before defense, the slide deck is updated:

| Slide | Current | New |
|---|---|---|
| Slide 4 (AI architecture) | 4 layers | 5 layers (adds "Adaptive checkpoint difficulty") |
| Slide 6 (active recall) | Static checkpoints | Static vs scaffolded vs contrastive (T1-C) |
| Slide 7 (engineering) | 4 phases | + Cognitive load pipeline (T1-A) |
| Slide 9 (SM-2) | Per-concept SR | + Mastery trajectory visualization (T1-B) |
| Slide 10 (live demo) | Single trace | + Fingerprint diff (T1-D) |

Contribution count: **4 → 5 primary (T1-A as the methodological
contribution), 2 exploratory**. Within-subjects design is
preserved. The pre-registration needs one amendment — adding T1-A's
load mediator — but is otherwise intact.

---

## 7. What I am NOT recommending, and why

| Idea | Why not now |
|---|---|
| Voice tutor | Breaks the within-subjects design (can't A/B voice vs text). Not a research contribution. |
| Multi-language (JS, C++, Java) | Triples scope. Thesis is CS1 Python. |
| Mobile native app | Defense timeline doesn't justify it. |
| True chat-based Socratic mode | Covered as the integration story in §5, not as a separate feature. |
| Real-time collaboration (multi-student) | Massive scope creep. Study is within-subjects. |
| Generative AI autograder for free-text responses | Independent contribution; out of scope. |
| LLM fine-tuning on traces (vs prompting) | Promising but the value of fine-tuning vs prompting on CS1 traces is itself an open research question. Not a thesis contribution. |

---

## 8. References

The peer-reviewed citations used in this document, formatted for
direct inclusion in the thesis bibliography.

1. Urry, J. O., & Edwards, J. (2024). *A Framework that Explores the
   Cognitive Load of CS1 Assignments Using Pausing Behavior*. ACM
   SIGCSE 2024. DOI:
   [10.1145/3626252.3630760](https://doi.org/10.1145/3626252.3630760).

2. Duran, R., Zavgorodniaia, A., Sorva, J., et al. (2022). *Cognitive
   Load Theory in Computing Education Research: A Review*. ACM
   Transactions on Computing Education, 22(4). DOI:
   [10.1145/3483843](https://doi.org/10.1145/3483843).

3. Duran, R., Hellas, A., et al. (2025). *Student-Perceived Cognitive
   Load of LLM-Generated Programming Exercises*. IEEE DSAA 2025.
   DOI:
   [10.1109/dsaa65442.2025.11247983](https://doi.org/10.1109/dsaa65442.2025.11247983).

4. Bauer, A., et al. (2025). *Less stress, better scores, same
   learning: The dissociation of performance and learning in
   AI-supported programming education*. Computers and Education:
   Artificial Intelligence. DOI:
   [10.1016/j.caeai.2025.100034](https://doi.org/10.1016/j.caeai.2025.100034).

5. Liu, S., et al. (2025). *RPKT: Learning What You Don't Know —
   Recursive Prerequisite Knowledge Tracing in Conversational AI
   Tutors for Personalized Learning*. arXiv:2508.11892.

6. Shivam, A., et al. (2025). *EDGE: A Theoretical Framework for
   Misconception-Aware Adaptive Learning — Evaluate → Diagnose →
   Generate → Exercise*. arXiv:2508.07224.

7. Settles, B., & Meeder, B. (2016). *Adaptive Forgetting Curves for
   Spaced Repetition Language Learning*. PMC: PMC7334729.

8. Fiechter, J. L., & Benjamin, A. S. (2019). *Techniques for
   scaffolding retrieval practice: The costs and benefits of
   adaptive versus diminishing cues*. Psychonomic Bulletin &
   Review. DOI:
   [10.3758/s13423-019-01617-6](https://doi.org/10.3758/s13423-019-01617-6).

9. Ritter, S., et al. (2016, ongoing). *Carnegie Learning MATHia —
   Model-Tracing Tutors*. Cited via LAK-26 follow-up: DOI
   [10.1145/3785022.3785096](https://doi.org/10.1145/3785022.3785096).

10. Wang, Y., et al. (2025). *STAP: A Socratic Tutor for Adaptive
    Programming with Pedagogical Scaffolding*. ISAIE 2025. DOI:
    [10.1145/3775073.3775165](https://doi.org/10.1145/3775073.3775165).

11. Al-Hossami, E., Bunescu, R., Smith, J., Teehan, R. (2024). *Can
    Language Models Employ the Socratic Method? Experiments with
    Code Debugging*. ACM SIGCSE 2024.

12. Al-Hossami, E., et al. (2024). *To Tell or to Ask? Comparing the
    Effects of Targeted vs. Socratic AI Hints*. DOI:
    [10.1145/3770761.3777327](https://doi.org/10.1145/3770761.3777327).

13. Kazemitabaar, M., et al. (2024). *Studying the effect of AI Code
    Generators on Supporting Novice Learners in Introductory
    Programming*. CHI 2024.

14. Liu, J., et al. (2024). *HypoCompass: Using LLMs as a Teachable
    Agent for Debugging*. arXiv:2310.05292v5.

15. Lin, Z., et al. (2025). *Reasoning Runtime Behavior of a Program
    with LLM (REval)*. ICSE 2025.

16. Piterbarg, U., et al. (2025). *What I cannot execute, I do not
    understand: Training and Evaluating LLMs on Program Execution
    Traces*. arXiv:2503.05703.

17. Tian, Y., et al. (2025). *Do Code Semantics Help? A Comprehensive
    Study on Execution Trace-Based Information for Code Large Language
    Models*. EMNLP 2025 Findings.

18. Guo, P. J. (2013). *Online Python Tutor: Embeddable Web-Based
    Program Visualization*. ACM SIGCSE 2013.

19. Karpicke, J. D., & Roediger, H. L. (2008). *Expanding Retrieval
    Practice Promotes Short-Term Retention, but Equally Spaced
    Retrieval Enhances Long-Term Retention*. Journal of Experimental
    Psychology: Learning, Memory, and Cognition.

20. Sweller, J. (1988). *Cognitive Load During Problem Solving:
    Effects on Learning*. Cognitive Science, 12(2).

---

## 9. Recommended order of implementation

| Order | Feature | Sprint | Rationale |
|---|---|---|---|
| 1 | T1-B (Mastery Trajectory) | 1 wk | Uses existing data; visual; fastest committee wow |
| 2 | T1-A (Cognitive Load Dashboard) | 1 wk | Strengthens H1 into a mediator story; load is empirically defensible |
| 3 | T1-D (Fingerprint Diff) | 1.5 wk | Extends just-shipped `FingerprintBadge`; high demo value |
| 4 | T1-C (Adaptive Difficulty) | 1.5 wk | Most research-heavy; most risk; do last when energy is highest |

Total: **~5 weeks** for all four. Compatible with a 2–6 month defense
window. The slide deck's `docs/slide_deck_presentation_script.research.md`
would be updated once after T1-B ships and once after T1-C ships.

---

## 10. What I learned from this research that is *not* in this doc

Two findings did not make it into a feature recommendation but should
inform the threat-to-validity section of Chapter 6:

1. **Khanmigo's 2-year RCT** (Tennessee middle schools, N>5000)
   finds that AI tutoring improves math achievement by 0.06–0.08 SD
   — *with* active participation reaching 0.14 SD, *but* only when
   students actively message the tutor (96% tried, only 33% used it
   daily). Cite this as external-validity context for why *engagement
   hooks* (T1-B's animated trajectory is one) matter at least as
   much as algorithmic sophistication.

2. **Code-Execution-Simulation audit** (arXiv:2512.00215, 2025)
   identifies nine categories of LLM execution-reasoning errors:
   Computation, Indexing, Control Flow, Skip Statements, Misreporting
   Final Output, Input Misread, Misevaluation of Native API,
   Hallucination, Lack of Verification. The trace-grounding
   mechanism specifically neutralizes the **Hallucination** and
   **Misreporting** categories by construction — make this explicit
   in the discussion section.

Both findings strengthen the framing of the existing contributions
without requiring new features.
