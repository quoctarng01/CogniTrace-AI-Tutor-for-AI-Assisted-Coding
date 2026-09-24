# scripts/ — RQ1 evaluation, smoke tests, DB helpers

This folder holds small standalone Python scripts that drive CogniTrace's
empirical evaluation and dev-environment work.

## `evaluate_task_battery.py` — the RQ1 evaluation runner

Runs the 6-bug debugging battery × 3 conditions × N runs through an LLM
judge and writes results CSV + Cohen's d.

### Quick start

```bash
# 1. Add one of these to backend/.env:

# RECOMMENDED — Groq, free, 14,400 req/min, no credit card
# Get a key at https://console.groq.com/keys
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-120b

# OR fallback — GitHub Models, 50 free req/month
# Get a token at https://github.com/settings/tokens (Models: read scope)
GITHUB_MODELS_PAT=ghp_...
GITHUB_MODELS_MODEL=openai/gpt-4o-mini

# 2. Run the evaluation
python scripts/evaluate_task_battery.py --provider groq --output results/
#                                                ^^^ default; can omit
# 3. Inspect outputs
ls results/
#   task_battery_results.csv    # 54 rows (6 tasks × 3 conditions × 3 runs)
#   task_battery_summary.csv    # mean ± sd per task × condition
#   cohens_d.csv                # Cohen's d per task (B vs C, A vs C)
```

### Why Groq?

| Provider | Free tier | Latency | Cost | Card? |
|----------|-----------|---------|------|-------|
| **Groq** (default) | 14,400 req/min | ~300ms | $0 | No |
| **GitHub Models** | 50 req/month | ~1500ms | $0 | No |
| OpenAI API | $5 credit | ~1500ms | ~$0.50 per 54 calls | Yes |
| Anthropic | $5 credit | ~2000ms | ~$1 per 54 calls | Yes |

For RQ1 we run 54 evaluations. On Groq this takes ~30 seconds with `--runs 3`
or ~90 seconds with `--runs 10`. On GitHub Models you would burn the entire
free tier on one run.

### What the three conditions measure

- **A — Python Tutor baseline:** "You are a CS1 student using Python Tutor. Run this code mentally and identify the bug."
- **B — Ungrounded LLM chat:** "You are a helpful CS1 coding assistant. The following Python code has a bug. Identify and fix it."
- **C — CogniTrace (trace-grounded):** "You are a CogniTrace AI tutor. The following Python code was executed step-by-step. The runtime state at key lines is shown below..." with simulated trace frames.

### Customizing the run

```bash
# More runs for tighter variance estimation
python scripts/evaluate_task_battery.py --runs 10

# Override model (e.g., Groq's best code model)
python scripts/evaluate_task_battery.py --model openai/gpt-oss-120b

# Fallback provider
python scripts/evaluate_task_battery.py --provider github

# Custom output directory
python scripts/evaluate_task_battery.py --output /tmp/rq1-pilot/

# Groq free tier: strict per-second rate-limit (30 req/s burst).
# Each task = 2 LLM calls. Default sleep=2.5s between tasks works.
# If you hit 429s, increase sleep or reduce --runs.
```

### Pre-registration

The 6-task battery (`docs/study-instruments/task-battery-v1.md`) and the
LLM judge rubric are **fixed before the evaluation runs**. Tasks are not
modified based on results. This is documented in
`docs/THESIS-00-RESEARCH-QUESTIONS.md` §7.

### Limitations to disclose in the thesis

- LLM-as-judge is a proxy for novice debugging behavior. It does not measure
  actual student cognition. (Future work: validate with N=10 human pilot.)
- Same-model evaluation (judge and tool are the same LLM) introduces some
  self-preference bias. Mitigation: future runs can use a different judge model.
- 3 runs per condition is at the lower bound of statistical power. Use
  `--runs 10` if you have time.

---

## Other scripts (in progress)

| Script | Purpose | Status |
|--------|---------|--------|
| `evaluate_task_battery.py` | RQ1 LLM-as-judge runner | ✅ Ready |
| `validate_migrations.py` | Pre-flight DB schema validator | WIP |
| `backup_db.sh` | Local Supabase backup | WIP |
| `load_test_traces.py` | k6-like load test for the trace runner | WIP |
