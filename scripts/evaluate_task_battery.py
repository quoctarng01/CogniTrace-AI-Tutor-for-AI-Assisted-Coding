#!/usr/bin/env python3
"""
evaluate_task_battery.py — Automated debugging evaluation for CogniTrace RQ1.

Runs all 6 tasks × 3 conditions through the LLM judge and produces a
results CSV for statistical analysis.

Usage:
    # From repo root — CSVs go to <repo>/results/
    python scripts/evaluate_task_battery.py --provider groq

    # From any cwd, override the output directory
    python scripts/evaluate_task_battery.py --provider github --output ./out/
    python scripts/evaluate_task_battery.py --provider groq  --output /absolute/path

Prerequisites (one of):
    - Groq API key  (recommended — free, fast, 14,400 req/min)
      Set GROQ_API_KEY in backend/.env
    - GitHub Models PAT (fallback — 50 free req/month)
      Set GITHUB_MODELS_PAT in backend/.env

Get a Groq API key:  https://console.groq.com/keys  (no credit card, ~2 min)
Get a GitHub PAT:   https://github.com/settings/tokens (requires Models: read)

Outputs:
    results/task_battery_results.csv   — raw scores per task/condition/run
    results/task_battery_summary.csv   — mean scores and std per task×condition
    results/cohens_d.csv              — Cohen's d per task (B vs C, A vs C)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import math
import re
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Add backend to path so we can import app modules ────────────────────────
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT / "backend"))

import httpx

# ── LLM Judge ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT_JUDGE = """You are an expert CS1 instructor evaluating debugging responses.
Score the student's debugging work on a scale of 0–2:

Score 2 (EXCELLENT): Correctly identifies the bug, explains why it causes the wrong
  behavior, and provides the correct fix.

Score 1 (PARTIAL): Identifies that something is wrong but misattributes the cause,
  or identifies the correct fix without explaining the mechanism.

Score 0 (INCORRECT): No relevant diagnosis, or diagnosis is clearly wrong.

Respond in JSON format only:
{
  "score": 0,
  "reasoning": "one sentence explaining the score",
  "bug_identified": "what was correctly identified (or 'none')",
  "fix_provided": "yes | no | partial"
}"""

CONDITION_PROMPTS: dict[str, str] = {
    "A": (
        "You are a CS1 student using Python Tutor. "
        "Run the following Python code step-by-step. "
        "Observe the output. Then identify and fix the bug. "
        "Provide the corrected code only."
    ),
    "B": (
        "You are a helpful CS1 coding assistant. "
        "The following Python code has a bug. "
        "Identify and fix it. Provide the corrected code."
    ),
    "C": (
        "You are a CogniTrace AI tutor. "
        "The following Python code was executed step-by-step. "
        "The runtime state at key lines is shown below. "
        "Use the runtime state to understand what is actually happening. "
        "Then identify and fix the bug. Reference the specific runtime values. "
        "Provide the corrected code."
    ),
}


@dataclass
class TaskResult:
    run_id: str
    task_id: str
    condition: str
    score: int
    reasoning: str
    bug_identified: str
    fix_provided: str
    latency_ms: int
    judged_at: str
    raw_response: str = ""


@dataclass
class TaskSpec:
    task_id: str
    title: str
    concept: str
    difficulty: str
    buggy_code: str
    fixed_code: str
    bug_line: int
    bug_description: str
    bug_category: str


# ── Multi-provider LLM client (Groq primary, GitHub Models fallback) ─────

# Provider config: endpoint, default model, env-var for API key.
PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "default_model": "openai/gpt-oss-120b",
        "env_key": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "doc": (
            "Get a free key at https://console.groq.com/keys\n"
            "Free tier: 14,400 req/min, 30 req/s. No credit card needed.\n"
            "Model: openai/gpt-oss-120b (Groq's best code model)\n"
            "NOTE: gpt-oss-120b is a reasoning model (thinks before answering).\n"
            "      It needs 512+ max_tokens to output content. The eval script\n"
            "      uses 600 tokens for tool calls and 300 for the judge."
        ),
    },
    "github": {
        "base_url": "https://models.inference.ai.azure.com/v1/chat/completions",
        "default_model": "openai/gpt-4o-mini",
        "env_key": "GITHUB_MODELS_PAT",
        "model_env": "GITHUB_MODELS_MODEL",
        "doc": (
            "Free tier: 50 req/month (very tight for batch eval).\n"
            "Get a token at https://github.com/settings/tokens (Models: read scope).\n"
            "Model: openai/gpt-4o-mini"
        ),
    },
}


def _read_env(provider: str) -> tuple[str, str]:
    """Read API key and model from backend/.env for the given provider."""
    if provider not in PROVIDER_CONFIG:
        raise ValueError(
            f"Unknown provider '{provider}'. Choose: {list(PROVIDER_CONFIG)}"
        )
    cfg = PROVIDER_CONFIG[provider]

    env_path = ROOT / "backend" / ".env"
    if not env_path.exists():
        raise RuntimeError(
            f"backend/.env not found at {env_path}. "
            "Copy .env.template-pilot to .env and fill in your API key."
        )

    api_key, model = "", cfg["default_model"]
    for line in env_path.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k == cfg["env_key"]:
            api_key = v
        elif k == cfg["model_env"]:
            if v:
                model = v

    if not api_key:
        raise RuntimeError(
            f"{cfg['env_key']} not set in backend/.env.\n{cfg['doc']}"
        )
    return api_key, model


async def call_llm(
    prompt: str,
    system: str,
    model: str,
    provider: str,
    api_key: str,
    temperature: float = 0.3,
    max_tokens: int = 600,
    max_retries: int = 5,
) -> tuple[str, int]:
    """Call LLM via Groq or GitHub Models with automatic 429 retry.

    Retries on 429 (rate-limit) with exponential backoff.  Groq's free tier
    has a 30 req/s burst limit — two sequential calls ~3s apart naturally
    avoids this, but a retry guard is still useful.
    """
    cfg = PROVIDER_CONFIG[provider]
    url = cfg["base_url"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if provider == "groq":
        payload["stream"] = False

    for attempt in range(max_retries):
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
        latency_ms = int((time.perf_counter() - start) * 1000)

        if resp.status_code == 200:
            data: dict[str, Any] = resp.json()
            return data["choices"][0]["message"]["content"].strip(), latency_ms

        if resp.status_code == 429:
            if attempt < max_retries - 1:
                backoff = min(2.0 ** attempt, 32.0)  # 1s, 2s, 4s, 8s, 16s (cap 32)
                logging.warning(
                    "[retry %d/%d] 429 from %s - backing off %.1fs",
                    attempt + 1, max_retries, provider, backoff,
                )
                await asyncio.sleep(backoff)
                continue
            raise RuntimeError(
                f"Rate-limited by {provider} after {max_retries} attempts. "
                "Use --provider github or wait and retry."
            )

        raise RuntimeError(
            f"{provider} API error {resp.status_code}: {resp.text[:300]}"
        )

    raise RuntimeError("unreachable")  # satisfies type checker


def parse_judge_response(raw: str) -> dict[str, Any]:
    """Extract JSON from judge response, handling markdown code fences."""
    cleaned = re.sub(r"```json\s*", "", raw, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```\s*", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r'"score"\s*:\s*(\d+)', raw)
        if m:
            return {
                "score": int(m.group(1)),
                "reasoning": "[parse failed]",
                "bug_identified": "none",
                "fix_provided": "no",
            }
        return {
            "score": 0,
            "reasoning": f"[JSON parse failed: {raw[:100]}]",
            "bug_identified": "none",
            "fix_provided": "no",
        }


# ── Simulate trace frames for Condition C ─────────────────────────────────

def simulate_trace_frames(code: str) -> str:
    """Lightweight tracer: shows variable names and repr values at each line.

    This produces approximate trace frames for the automated evaluation without
    running the full CogniTrace system. The actual system produces more detailed
    frames at runtime.
    """
    import sys as _sys

    frames: list[str] = []
    old = _sys.gettrace()

    def tracer(frame: Any, event: str, _arg: Any) -> Any:
        if event in ("call", "line"):
            lineno = frame.f_lineno
            locals_: dict[str, Any] = {
                k: repr(v)[:40]
                for k, v in frame.f_locals.items()
                if not k.startswith("__") and not callable(v)
            }
            frames.append(f"  Line {lineno}: {locals_}")
        return tracer

    _sys.settrace(tracer)
    try:
        exec(code, {})
    except Exception:
        pass
    finally:
        _sys.settrace(old)

    return "\n".join(frames[:20]) if frames else "(trace unavailable)"


# ── Load task battery ────────────────────────────────────────────────────

def load_task_battery(path: Path) -> list[TaskSpec]:
    """Parse the task battery markdown file into TaskSpec objects."""
    content = path.read_text(encoding="utf-8")
    tasks: list[TaskSpec] = []

    # Split on ## Task B## headings.  Use a look-ahead so the heading
    # stays at the start of each chunk (needed to extract the task ID).
    chunks = re.split(r"\n(?=## Task B\d+)", content)
    for chunk in chunks[1:]:  # skip the preamble
        tid_m = re.search(r"## Task (B\d+)", chunk)
        task_id = tid_m.group(1) if tid_m else "B??"

        title_m = re.search(r"task_id: (B\d+)\s+title:\s*\"([^\"]+)\"", chunk)
        title = title_m.group(2) if title_m else "?"

        concept_m = re.search(r"concept:\s*([^\n]+)", chunk)
        concept = concept_m.group(1).strip() if concept_m else "?"

        diff_m = re.search(r"difficulty:\s*([^\n]+)", chunk)
        difficulty = diff_m.group(1).strip() if diff_m else "?"

        code_blocks = re.findall(r"```python\n(.*?)```", chunk, re.DOTALL)
        buggy_code = code_blocks[0].strip() if len(code_blocks) > 0 else ""
        fixed_code = code_blocks[1].strip() if len(code_blocks) > 1 else ""

        bug_line_m = re.search(r"\*\*Bug line:\*\* (\d+)", chunk)
        bug_line = int(bug_line_m.group(1)) if bug_line_m else 0

        bug_desc_m = re.search(r"\*\*Bug description:\*\* (.*?)(?:\n|$)", chunk)
        bug_description = bug_desc_m.group(1).strip() if bug_desc_m else ""

        bug_cat_m = re.search(r"bug_category:\s*([^\n]+)", chunk)
        bug_category = bug_cat_m.group(1).strip() if bug_cat_m else ""

        tasks.append(
            TaskSpec(
                task_id=task_id,
                title=title,
                concept=concept,
                difficulty=difficulty,
                buggy_code=buggy_code,
                fixed_code=fixed_code,
                bug_line=bug_line,
                bug_description=bug_description,
                bug_category=bug_category,
            )
        )

    return tasks


# ── Evaluation ────────────────────────────────────────────────────────────

async def evaluate_task(
    task: TaskSpec,
    condition: str,
    run_id: str,
    model: str,
    provider: str,
    api_key: str,
) -> TaskResult:
    """Evaluate one task under one condition. Two LLM calls: tool + judge."""
    # ── Build evaluation prompt ────────────────────────────────────────────
    if condition == "A":
        user_prompt = (
            "You are a CS1 student using Python Tutor.\n"
            "Run the following code mentally and identify the bug.\n"
            "Provide the corrected code only.\n\n"
            f"Buggy code:\n```python\n{task.buggy_code}\n```\n"
            f"Bug description (for your reference): {task.bug_description}\n"
        )
    elif condition == "B":
        user_prompt = (
            f"{CONDITION_PROMPTS['B']}\n\n"
            f"Buggy code:\n```python\n{task.buggy_code}\n```\n"
            f"Bug description (for your reference): {task.bug_description}\n"
        )
    elif condition == "C":
        trace_frames = simulate_trace_frames(task.buggy_code)
        user_prompt = (
            f"{CONDITION_PROMPTS['C']}\n\n"
            f"Buggy code:\n```python\n{task.buggy_code}\n```\n\n"
            f"Runtime trace:\n{trace_frames}\n\n"
            f"Bug description (for your reference): {task.bug_description}\n"
        )
    else:
        raise ValueError(f"Unknown condition: {condition}")

    tool_system = {
        "A": "You are a CS1 student using Python Tutor.",
        "B": CONDITION_PROMPTS["B"],
        "C": CONDITION_PROMPTS["C"],
    }[condition]

    raw_response, latency_ms = await call_llm(
        user_prompt, tool_system, model, provider, api_key,
        temperature=0.3, max_tokens=600,
    )

    # Small gap between tool call and judge call; longer gap before next task's
    # student call.  Groq free tier = 30 RPM = ~1 req/2s.  Spacing student
    # calls by ≥2s avoids 429s on the very next request.
    # (The 2.5 s post-task sleep already handles the average rate, but Groq's
    # bucket is per-second so we also need a minimum gap between each pair.)
    gap_s = 2.0 if provider == "groq" else 0.1
    await asyncio.sleep(gap_s)

    # ── Judge ────────────────────────────────────────────────────────────
    judge_user = (
        "Score this CS1 debugging response.\n\n"
        f"Buggy code:\n```python\n{task.buggy_code}\n```\n\n"
        f"Expected fix:\n```python\n{task.fixed_code}\n```\n\n"
        f"Bug description: {task.bug_description}\n\n"
        f"Student's response:\n{raw_response[:800]}\n"
    )
    judge_raw, judge_latency = await call_llm(
        SYSTEM_PROMPT_JUDGE,
        judge_user,
        model,
        provider,
        api_key,
        temperature=0.1,
        max_tokens=300,
    )

    judged = parse_judge_response(judge_raw)
    return TaskResult(
        run_id=run_id,
        task_id=task.task_id,
        condition=condition,
        score=judged.get("score", 0),
        reasoning=judged.get("reasoning", ""),
        bug_identified=judged.get("bug_identified", "none"),
        fix_provided=judged.get("fix_provided", "no"),
        latency_ms=latency_ms + judge_latency,
        judged_at=datetime.now(timezone.utc).isoformat(),
        raw_response=raw_response[:400],
    )


async def run_evaluation(
    tasks: list[TaskSpec],
    output_dir: Path,
    model: str,
    provider: str,
    api_key: str,
    runs_per_condition: int = 3,
    max_concurrent: int = 1,
) -> list[TaskResult]:
    """Run full factorial: runs × tasks × conditions.

    max_concurrent: how many tasks may be in-flight simultaneously.
    Use 1 for Groq free tier (strict rate-limit). Use 3+ for paid tiers.
    """
    results: list[TaskResult] = []
    conditions = ["A", "B", "C"]

    # Semaphore enforces the concurrency ceiling.
    sem = asyncio.Semaphore(max_concurrent)

    # Pause between requests: GitHub needs ~1s; Groq free tier needs ≥2.5s.
    # Each task = 2 calls (tool + judge) ~3s apart. Groq allows 30 req/s burst.
    # 2.5s sleep → ~8 tasks/min ≈ 16 calls/min, well within 14,400 req/min limit.
    sleep_s = 1.0 if provider == "github" else 2.5

    for run_idx in range(1, runs_per_condition + 1):
        for task in tasks:
            for cond in conditions:
                rid = f"run{run_idx:02d}_{task.task_id}_{cond}"
                async with sem:
                    logging.info("[%s] Evaluating...", rid)
                    try:
                        result = await evaluate_task(
                            task, cond, rid, model, provider, api_key
                        )
                        results.append(result)
                        reason_preview = (
                            result.reasoning[:50]
                            .replace("\u2011", "-")
                            .replace("\u2013", "-")
                            .replace("\u2014", "--")
                            .replace("\u2018", "'").replace("\u2019", "'")
                            .replace("\u201c", '"').replace("\u201d", '"')
                        )
                        logging.info(
                            "[%s] Score=%d (%s) latency=%dms",
                            rid, result.score, reason_preview, result.latency_ms,
                        )
                    except Exception as exc:
                        logging.error("[%s] FAILED: %s", rid, exc)
                        results.append(
                            TaskResult(
                                run_id=rid,
                                task_id=task.task_id,
                                condition=cond,
                                score=-1,
                                reasoning=f"ERROR: {exc}",
                                bug_identified="none",
                                fix_provided="no",
                                latency_ms=0,
                                judged_at=datetime.now(timezone.utc).isoformat(),
                            )
                        )
                await asyncio.sleep(sleep_s)  # rate-limit buffer

    return results


# ── Statistics helpers ───────────────────────────────────────────────────

def _mean(vals: list[float]) -> float:
    return statistics.mean(vals)


def _variance(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = statistics.mean(vals)
    return sum((v - m) ** 2 for v in vals) / (len(vals) - 1)


def cohens_d(a: list[float], b: list[float]) -> float:
    """Cohen's d: standardized mean difference between two groups.

    Returns NaN when either group has fewer than 2 observations (undefined d),
    or when the pooled SD is zero (identical means).
    """
    if len(a) < 2 or len(b) < 2:
        return float("nan")  # d is undefined for n<2 per group
    n1, n2 = len(a), len(b)
    var_a = _variance(a)
    var_b = _variance(b)
    pooled = math.sqrt(((n1 - 1) * var_a + (n2 - 1) * var_b) / (n1 + n2 - 2))
    if pooled == 0.0:
        return float("nan")  # identical means — no effect size
    return (statistics.mean(b) - statistics.mean(a)) / pooled


# ── Save results ──────────────────────────────────────────────────────

def _s(val: str) -> str:
    """ASCII sanitizer for cross-platform CSV readability (PowerShell cp949-safe)."""
    return (
        val.encode("ascii", "replace").decode("ascii")
        .replace("\u2011", "-").replace("\u2013", "-")
        .replace("\u2014", "--").replace("\u2018", "'")
        .replace("\u2019", "'").replace("\u201c", '"')
        .replace("\u201d", '"').replace("\u00a0", " ")
        .replace("\u2022", "*").replace("\u2026", "...")
        .replace("\u00b7", "-")
    )


def _fmt(val: float) -> str:
    """Format a float or NaN for CSV output."""
    if math.isnan(val):
        return "NA"
    return str(round(val, 3))


def save_results(results: list[TaskResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Raw results
    raw_path = output_dir / "task_battery_results.csv"
    with open(raw_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "run_id", "task_id", "condition", "score",
            "bug_identified", "fix_provided", "latency_ms",
            "reasoning", "judged_at",
        ])
        for r in results:
            w.writerow([
                r.run_id, _s(r.task_id), r.condition, r.score,
                _s(r.bug_identified), _s(r.fix_provided), r.latency_ms,
                _s(r.reasoning).replace('"', '""'), r.judged_at,
            ])
    logging.info("Raw results → %s", raw_path)

    # 2. Summary: mean ± sd per task × condition
    scores: dict[tuple[str, str], list[int]] = defaultdict(list)
    for r in results:
        if r.score >= 0:
            scores[(r.task_id, r.condition)].append(r.score)

    summary_path = output_dir / "task_battery_summary.csv"
    with open(summary_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "condition", "n", "mean_score", "std_score"])
        for (tid, cond), vals in sorted(scores.items()):
            m = statistics.mean(vals)
            s = statistics.stdev(vals) if len(vals) > 1 else 0.0
            w.writerow([tid, cond, len(vals), round(m, 3), round(s, 3)])
    logging.info("Summary → %s", summary_path)

    # 3. Cohen's d per task
    task_ids = sorted({t for t, _ in scores.keys()})
    d_path = output_dir / "cohens_d.csv"
    with open(d_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "task_id", "d_B_vs_C", "d_A_vs_C",
            "mean_B", "mean_C", "mean_A",
        ])
        for tid in task_ids:
            b_v = [float(v) for v in scores.get((tid, "B"), [])]
            c_v = [float(v) for v in scores.get((tid, "C"), [])]
            a_v = [float(v) for v in scores.get((tid, "A"), [])]
            d_bc = cohens_d(b_v, c_v)
            d_ac = cohens_d(a_v, c_v)
            w.writerow([
                tid,
                _fmt(d_bc),
                _fmt(d_ac),
                round(statistics.mean(b_v), 3) if b_v else "NA",
                round(statistics.mean(c_v), 3) if c_v else "NA",
                round(statistics.mean(a_v), 3) if a_v else "NA",
            ])
    logging.info("Cohen's d → %s", d_path)


# ── CLI ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run CogniTrace RQ1 automated evaluation."
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "results",
        help="Output directory for CSVs (default: <repo>/results)",
    )
    parser.add_argument(
        "--runs", type=int, default=3,
        help="Evaluation runs per task×condition (default 3)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="groq",
        choices=list(PROVIDER_CONFIG.keys()),
        help="LLM provider (default: groq)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override model name (default: provider's default)",
    )
    parser.add_argument(
        "--max-concurrent", type=int, default=1,
        help="Max simultaneous LLM requests (default: 1; use 1-3 for Groq free tier)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Load credentials for the chosen provider
    api_key, default_model = _read_env(args.provider)
    model = args.model or default_model
    logging.info("Provider: %s  Model: %s", args.provider, model)

    # Load battery
    battery_path = ROOT / "docs" / "study-instruments" / "task-battery-v1.md"
    if not battery_path.exists():
        logging.error(
            "Task battery not found at %s. "
            "Create docs/study-instruments/task-battery-v1.md first.",
            battery_path,
        )
        sys.exit(1)

    tasks = load_task_battery(battery_path)
    logging.info("Loaded %d tasks: %s", len(tasks), [t.task_id for t in tasks])

    # Run
    results = asyncio.run(
        run_evaluation(
            tasks=tasks,
            output_dir=args.output,
            model=model,
            provider=args.provider,
            api_key=api_key,
            runs_per_condition=args.runs,
            max_concurrent=args.max_concurrent,
        )
    )

    # Save
    save_results(results, args.output)

    # Print quick summary
    cond_scores: dict[str, list[int]] = defaultdict(list)
    for r in results:
        if r.score >= 0:
            cond_scores[r.condition].append(r.score)

    print("\n" + "=" * 50)
    print("EVALUATION SUMMARY")
    print("=" * 50)
    print(f"  Provider: {args.provider}  Model: {model}")
    for cond in ["A", "B", "C"]:
        vals = cond_scores[cond]
        if vals:
            print(
                f"  Condition {cond}: mean={statistics.mean(vals):.2f} "
                f"sd={statistics.stdev(vals):.2f} n={len(vals)}"
            )
    print(f"\nOutputs → {args.output}/")
    print(f"  task_battery_results.csv  ({len(results)} rows)")
    print(f"  task_battery_summary.csv")
    print(f"  cohens_d.csv")


if __name__ == "__main__":
    main()
