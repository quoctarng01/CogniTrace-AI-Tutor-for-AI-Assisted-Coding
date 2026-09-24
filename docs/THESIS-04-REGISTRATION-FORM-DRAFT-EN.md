# Thesis Registration Form — Completed Draft (English Only)

> **Print and fill by hand, or copy into the PDF form.** All claims are traceable to
> pre-registered artifacts in this repo (see the mapping table at the end).

---

## Student Information

| Field | Value |
|---|---|
| Student's name | _______________________________ |
| Student ID | _______________________________ |
| Email | _______________________________ |
| Phone | _______________________________ |
| Major | Computer Science |
| Supervisor 1 | _______________________________ *(leave blank until signed)* |

---

## Thesis Title

> Submitted title (locked):

**A State-Grounded AI Tutor for Personalized Programming Support Using Large Language Models**

> Throughout this form, "state-grounded" is interpreted along two axes simultaneously: the **runtime state** of the program (variables, branch outcomes, call frames — captured by execution fingerprints) and the **cognitive state** of the learner (mastery, cognitive load, misconception history). The unification of these two grounding signals in a single tutor loop is the central contribution.

**Earlier alternatives considered (kept here for record only):**

- *Trace-Grounded AI Tutoring for Python Debugging: An Empirical Study of Runtime-State Grounding for LLM Explanations in CS1*
- *Does Trace-Grounded AI Explanation Improve CS1 Debugging? An Empirical Study of CogniTrace.*
- *Grounding LLM Explanations in Runtime State: A Within-Subjects Study of CogniTrace vs. Ungrounded Chat for CS1 Debugging.*

---

## Thesis Goals and Objectives

### Goal 1 — Empirical (primary)

*Quantify whether CogniTrace's state-grounded AI tutoring — every prompt conditioned on both the runtime state of the student's code (trace grounding) and the cognitive state of the learner (mastery + load + misconception history) — improves transfer-task debugging accuracy for CS1 students compared to (a) Python Tutor alone and (b) Python Tutor + ungrounded LLM chat.*

- **Pre-registered primary hypothesis H1** (see `docs/THESIS-00-RESEARCH-QUESTIONS.md` §1)
- **Predicted effect:** ≥ +20 percentage points absolute improvement on transfer-task accuracy over ungrounded control; Cohen's d ≥ 0.6; α = 0.05, Bonferroni-corrected for three pairwise comparisons
- **Sample:** N = 24 first-year CS students, within-subjects, Latin-square counterbalancing
- **Primary outcome:** bug-identification accuracy and time-to-fix on a 6-bug task battery; transfer-task accuracy on novel code using the same concept
- **Secondary outcomes:** pre/post quiz delta (Cronbach's α ≥ 0.7), System Usability Scale, optional semi-structured interview (n = 10)
- **Decomposition analysis (planned):** isolate the runtime-state contribution (CogniTrace with runtime grounding on, learner grounding off) from the learner-state contribution (CogniTrace with learner grounding on, runtime grounding off) to support the dual-axis claim in the submitted title.

### Goal 2 — System

*Deliver a secure, production-deployable Python tracing platform combining (1) runtime-state-grounded retrieval-augmented generation (trace → LLM prompt context), (2) learner-state-grounded prompt construction (load + mastery + misconception history injected into every prompt), (3) LLM-generated active-recall checkpoints at control-flow branches, and (4) adaptive spaced repetition keyed to trace-derived concept tags.*

- Platform: **CogniTrace**, already implemented (this repository)
- Technical documentation: `docs/ARCHITECTURE.md`, `README.engineering.md`
- Security: two-tier sandbox (AST validation + subprocess isolation with resource caps and denylists); documented in `docs/SECURITY-SANDBOX.md`
- Testing: 365+ backend unit/integration tests, 100% coverage on tracer module, ≥ 25% overall with CI gate; Vitest + Playwright E2E for frontend
- Production artifacts: Docker Compose, GitHub Actions CI with coverage floor, DB backup script, load test, pre-commit hooks, content-addressed LLM cache, daily LLM-telemetry rollup

### Goal 3 — Methodological

*Pre-register the full study design (hypotheses, instruments, sample, analysis pipeline) before data collection begins; operate a reproducible measurement pipeline throughout.*

- Pre-registration record: `docs/THESIS-00-RESEARCH-QUESTIONS.md`
- Measurement surface: `docs/MEASUREMENT.md`
- Deviations logged in `docs/THESIS-DEVIATIONS.md` if any occur after registration
- Reproducibility: raw data, analysis scripts, and analysis-pipeline output included as thesis appendix

---

## Requirements

### Technical (mostly complete)

| # | Requirement | Status |
|---|---|---|
| 1 | Python 3.11+, FastAPI, Next.js 15/React 19/TypeScript, Supabase (Postgres + Auth), Redis | ✅ Built |
| 2 | Two LLM providers: Ollama Cloud (free, primary) + GitHub Models PAT (fallback) | ✅ Wired; keys needed at runtime |
| 3 | Database with 4 study tables: `traces`, `review_cards`, `explanations`, `llm_call_metrics`. Migrations V001–V013 in `backend/migrations/` | ✅ Shipped |
| 4 | Security sandbox: two-tier (AST validation + subprocess isolation with `setrlimit`, denylists for `match/case`, dunder access, generator DoS) | ✅ Implemented; documented in `docs/SECURITY-SANDBOX.md` |

### Data and participants

| # | Requirement | Status |
|---|---|---|
| 5 | IRB or departmental-equivalent approval (or Category 1 educational research exemption) | ⏳ To submit |
| 6 | 24 first-year CS participants (or 5–8 for the pilot if supervisor prefers a smaller scope) | ⏳ To recruit |
| 7 | 30-minute sessions; optional 10-minute interview for n = 10 | ⏳ To schedule |
| 8 | Anonymization: study-ID replaces user-ID; interview recordings deleted after transcription | ✅ Designed; pending IRB approval |

### Timeline (8-week window)

| Week | Deliverable |
|---|---|
| W1 | Pre-registration frozen; dev environment end-to-end; participant-consent flow live |
| W2 | Participant recruitment |
| W3 | Pilot sessions run |
| W4 | Manual grounding-review pass on explanation sample |
| W5 | Analysis notebook (p50/p95 latency, cache-hit rate, checkpoint accuracy, grounding rate) |
| W6 | Methods + Results chapter |
| W7 | Discussion, limitations, supervisor review |
| W8 | Final polish + defense prep |

> Note: RQ2 and RQ3 (exploratory) can be cut without invalidating Goal 1.

---

## Two-line summary for your supervisor

> *This thesis investigates whether runtime-state-grounded LLM explanations improve CS1 debugging comprehension compared to ungrounded LLM chat. The system is built; the remaining work is a pre-registered within-subjects study producing a defensible measurement of the trace-grounding effect in a 6-chapter thesis.*

---

## Signatures

| | Name | Signature | Date |
|---|---|---|---|
| Student | _______________________________ | _________________ | _____________ |
| Supervisor 1 | _______________________________ | _________________ | _____________ |

> Return signed form to the Undergraduate Academic Assistant of the Department.

---

## What to say at the meeting (30 seconds)

> *"The supervisor feedback on v1 was 'nothing special, nothing new.' I've reframed the work as a research thesis: same system, but with a pre-registered hypothesis (RQ1), a clear primary outcome (transfer-task accuracy), an effect-size threshold (d ≥ 0.6), and a within-subjects design with three conditions. The engineering is done. The remaining work is the empirical study over 8 weeks. I'd like your sign-off on this registration form."*

---

## What to say if the supervisor pushes back

| Pushback | Response |
|---|---|
| *"Why research questions? This is an engineering project."* | The form asks for "goals and objectives." Mine are written as measurable goals with hypothesis-grade thresholds. The pre-registration turns the engineering into research. |
| *"You don't have N=24."* | The pilot is N=5–8 (feasible in 8 weeks). RQ2/RQ3 can be cut. Goal 1 alone is sufficient for thesis defense. |
| *"The contribution isn't novel enough."* | The methodological contribution (cache hit rate as proxy for grounding reuse) and the pedagogical contribution (SM-2 soft-fail modification) are independently defensible. See `docs/THESIS-02-CONTRIBUTIONS.md` §6. |
| *"Just build a feature."* | The features are built (365+ tests, security hardening, LLM telemetry). The thesis is the deliverable; the features are the evidence. |

---

## Artifact mapping

| Form row | Source |
|---|---|
| Title | `docs/THESIS-00-ABSTRACT.md` §Title |
| Goal 1 | `docs/THESIS-00-RESEARCH-QUESTIONS.md` §1, §3, §5 |
| Goal 2 | `docs/ARCHITECTURE.md`, `README.engineering.md`, `docs/SECURITY-SANDBOX.md` |
| Goal 3 | `docs/MEASUREMENT.md`, `docs/THESIS-00-RESEARCH-QUESTIONS.md` §7 |
| Requirements | `docs/THESIS-01-STUDY-PROTOCOL.md` |
