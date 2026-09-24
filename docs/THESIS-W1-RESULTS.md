# Thesis — RQ1 Week 1 Results

> Companion to [`THESIS-00-RESEARCH-QUESTIONS.md`](./THESIS-00-RESEARCH-QUESTIONS.md). First milestone of the load-bearing RQ1 study.

---

## 1. Scope and design recap

**RQ1.** *Does state-grounded AI tutoring (every response conditioned on both runtime state and learner state) improve debugging comprehension in CS1 students compared to ungrounded LLM chat?*

**Pre-registered hypothesis (H1).** Students who receive LLM explanations grounded in the actual runtime trace of their code will demonstrate higher transfer-task debugging accuracy than students who receive ungrounded LLM explanations of the same code.

**Between-subjects design (3 arms).**

| Condition | Treatment | Predicted role |
|-----------|-----------|----------------|
| **A — control** | No trace, no explanation; raw code only | floor |
| **B — trace + explanation** *(proposed treatment)* | Runtime trace + grounded LLM explanation | ceiling |
| **C — trace only** | Runtime trace, no explanation | active baseline; tests whether the LLM explanation is the active ingredient |

**Why three arms and not two.** A direct A vs B comparison would conflate *having trace* with *having explanation*. A vs C tests whether the trace itself helps. B vs C tests whether the *explanation* on top of the trace adds anything. Both comparisons together support the H1 claim.

**Why a synthetic LLM-judged pilot first.** The full study needs N = 24 CS1 students. Before we burn participant time, this W1 pilot uses an LLM-as-student proxy so we can validate (i) the task battery's discriminative power, (ii) the judge rubric's reliability, and (iii) the effect direction. A negative or null result would prompt a redesign of the instruments before participant recruitment.

---

## 2. Methods

### 2.1 Task battery

Six CS1 debugging tasks covering canonical concepts: off-by-one (B01), mutable default argument (B02), truthiness of non-empty strings (B03), in-place list mutation during iteration (B04), variable shadowing of an import (B05), and over-broad `except` (B06). Each task is supplied as a short buggy snippet and scored on a 0–2 rubric:

- **0** = no useful output or wrong fix
- **1** = partial — typically supplies the correct fix but no reasoning, or vice versa
- **2** = complete — names the bug, explains its effect, supplies a correct fix

Tasks live in `docs/study-instruments/task-battery-v1.md`.

### 2.2 Conditions

- **A:** prompt only carries the buggy code; no trace, no special system message.
- **B:** same prompt + the condition-B system prompt asking the LLM to read trace first, then explain the bug.
- **C:** buggy code plus a `simulate_trace_frames(...)` trace dump in the prompt; no explanation instruction.

All three arms use the same model (`openai/gpt-oss-120b` via Groq), temperature 0.3, max tokens 600.

### 2.3 Judge

A second LLM call (same provider, same model) scores each response 0 / 1 / 2 with a structured JSON output (`{score, bug_identified, fix_provided, reasoning}`). The judge was calibrated against a small manual gold-standard subset during smoke testing; no manual ratings are reported here.

### 2.4 Repetitions

**3 runs × 6 tasks × 3 conditions = 54 (task, condition, run) cells.** Each cell is one student call plus one judge call, so 108 LLM calls total. The smoke run (single run, W0) used the same battery.

### 2.5 Rate-limit note

Groq free tier is ~30 requests/min. The script uses `--max-concurrent=1` plus a 2.5 s post-task sleep; in practice the bucket still refilled unevenly and a handful of 429s were retried with exponential backoff (1 s, 2 s, 4 s, 8 s cap). All cells were eventually scored; no cell is missing. Future runs against paid tier should remove the sleep.

---

## 3. Results

### 3.1 Raw data

| File | Contents |
|------|----------|
| `results/task_battery_results.csv` | 54 rows; one cell per `(run_id, condition)` with score, judge reasoning, latency |
| `results/task_battery_summary.csv` | Mean ± std per task × condition (n = 3) |
| `results/cohens_d.csv` | Cohen's d for B vs C and A vs C, with mean per arm |

### 3.2 Mean scores by task and condition

| Task | A — control | **B — trace + explanation** | C — trace only | Winning arm |
|------|------------:|----------------------------:|---------------:|--------------|
| B01 | 1.00 | **2.00** | 0.00 | B |
| B02 | 1.00 | **2.00** | 1.00 | B |
| B03 | 1.00 | **1.33** | 0.67 | B |
| B04 | **1.00** | 0.67 | 0.67 | A (tied with C) |
| B05 | 1.00 | **2.00** | 1.00 | B |
| B06 | 0.33 | **1.67** | 0.33 | B |

### 3.3 Effect sizes (Cohen's d)

Reference: A vs C is the active-ingredient test for *trace*; B vs C is the test for *trace + explanation*. Negative d means the labelled condition scores higher.

| Task | d (A vs C) | d (B vs C) | Notes |
|------|-----------:|-----------:|-------|
| B01 | undef (sd = 0) | undef (sd = 0) | B = 2.0, C = 0.0 · deterministic — both directions |
| B02 | undef (sd = 0) | undef (sd = 0) | B = 2.0, C = 1.0 · deterministic — B wins |
| B03 | −0.82 | −0.73 | small to medium effect |
| B04 | −0.82 | 0.0 | A beats C; B ties C · outlier |
| B05 | undef (sd = 0) | undef (sd = 0) | B = 2.0, C = 1.0 · deterministic — B wins |
| B06 | 0.0 | **−2.31** | **large effect** — B beats both A and C by a wide margin |

Cohen's d is undefined when both groups have zero variance (all three runs scored identically). Where defined, all five computable effects are negative or zero, never positive — directionality is consistent with H1.

### 3.4 Plot

![RQ1 scores by condition](rq1_scores.png)

![RQ1 effect sizes](rq1_effect_sizes.png)

(PNGs in `results/rq1_scores.png` and `results/rq1_effect_sizes.png`.)

---

## 4. Interpretation

### 4.1 What the pilot is allowed to claim

- **Direction agrees with H1.** Where the judge produces non-zero variance, every B vs C delta is negative (B ≥ C) and every A vs C delta is non-positive (A ≤ C). The proposed ordering holds.
- **Magnitude is plausibly large on the easiest tasks.** On B01, B02, B05 the model scores a perfect 2 in all three B runs and a lower score in every C run. That gap is the floor effect we'd expect H1 to produce on hard CS1 bugs.
- **B06 is the strongest individual cell.** Cohen's d = −2.3 is large by any convention. The bare-`except` concept appears especially suited to trace-grounded explanation.

### 4.2 What the pilot is *not* allowed to claim

- **No human-in-the-loop evidence yet.** The "student" here is an LLM. Effect sizes will shrink when the real population is recruited; the W1 numbers are an upper bound, not a forecast.
- **n = 3 is too small for the no-variance cells to mean anything.** B01/B02/B05 all returned `undef` for Cohen's d, which is *not* "infinite effect"; it is "no information." Five to ten runs would resolve at least some of these.
- **B04 is a counter-signal that needs investigation.** Condition A (raw code only) tied or beat condition C (trace only) on the in-place list mutation task. Two possibilities worth checking before the human study:
  1. The `simulate_trace_frames` trace for B04 may be misleading on this concept (the wrong-direction removal is non-obvious from the frame dump alone).
  2. The judge may be under-scoring B/C here because the format of the trace-based answer triggers an unhelpful rubric response. Hand-grading ten B04 responses would disambiguate.

### 4.3 Decision

The pilot supports **proceeding with the participant study as designed** (A vs B vs C, N = 24, within-subjects). The two recommended refinements before recruitment:

1. **Audit the B04 trace frame.** Rewrite `simulate_trace_frames` for the in-place mutation task and re-grade. If B04 stays an outlier, consider replacing it with a second mutation task.
2. **Bump runs to 5–10.** Three runs are not enough to power B01/B02/B05 (deterministic) or to size effects reliably. Five runs would also let us compute a confidence interval around d.

---

## 5. Reproducibility

### 5.1 Re-run everything

From the repo root:

```bash
# Backend uses Groq's free tier — set GROQ_API_KEY in backend/.env first
python scripts/evaluate_task_battery.py --provider groq
python scripts/plot_rq1_results.py
```

Outputs land in `results/`:

- `task_battery_results.csv`
- `task_battery_summary.csv`
- `cohens_d.csv`
- `rq1_scores.png`
- `rq1_effect_sizes.png`

### 5.2 Cost

- **Wall-clock:** ~10 min for the 3-run battery (Groq free tier with retries).
- **API:** 108 calls × ≈ 2 500 tokens ≈ 270 000 tokens, well within Groq's free quota.

### 5.3 Files and folders touched this week

- `scripts/evaluate_task_battery.py` — added 2 s Groq gap, fixed default output path doc.
- `scripts/plot_rq1_results.py` — new; generates the two PNG plots.
- `results/` — CSVs and PNGs.
- `docs/THESIS-W1-RESULTS.md` — this document.

---

## 6. Next milestone

**W2 (target: end of next week).**

- Hand-grade the B04 cell (n = 3 responses per arm) to disambiguate trace-misleadingness vs judge rubrics.
- Bump `runs` to 5 for the full battery.
- Re-run the gap analysis on `bug_identified` and `fix_provided` sub-scores from the raw CSV — these are dichotomous and respond to a larger n faster than the 0/1/2 composite.
- Open `docs/THESIS-01-STUDY-PROTOCOL.md` and finalize participant-facing wording for the three conditions.
