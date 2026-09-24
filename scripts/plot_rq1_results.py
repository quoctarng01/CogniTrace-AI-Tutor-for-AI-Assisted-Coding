#!/usr/bin/env python3
"""
plot_rq1_results.py — Visualize RQ1 debugging task results.

Reads:
    results/task_battery_summary.csv
    results/cohens_d.csv

Writes:
    results/rq1_scores.png        — grouped bar chart per condition
    results/rq1_effect_sizes.png  — effect-size plot (Cohen's d)

Usage:
    python scripts/plot_rq1_results.py
    python scripts/plot_rq1_results.py --results /path/to/results
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display in headless envs
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).parent.parent.resolve()
DEFAULT_RESULTS = ROOT / "results"

CONDITION_LABELS = {
    "A": "A · control",
    "B": "B · trace + explanation",
    "C": "C · trace only",
}
CONDITION_COLORS = {
    "A": "#9ca3af",  # gray
    "B": "#2563eb",  # blue
    "C": "#f59e0b",  # amber
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def plot_scores(summary_rows: list[dict[str, str]], out_path: Path) -> None:
    """Grouped bar chart: x=task, y=mean score (0-2), color=condition."""
    tasks = sorted({r["task_id"] for r in summary_rows})
    conditions = ["A", "B", "C"]
    means = {(r["task_id"], r["condition"]): float(r["mean_score"])
             for r in summary_rows}
    stds = {(r["task_id"], r["condition"]): float(r["std_score"])
            for r in summary_rows}

    x = np.arange(len(tasks))
    width = 0.26

    fig, ax = plt.subplots(figsize=(8.5, 5.0), dpi=160)
    for i, cond in enumerate(conditions):
        ys = [means[(t, cond)] for t in tasks]
        yerr = [stds[(t, cond)] for t in tasks]
        offset = (i - 1) * width
        bars = ax.bar(
            x + offset, ys, width,
            label=CONDITION_LABELS[cond],
            color=CONDITION_COLORS[cond],
            edgecolor="black", linewidth=0.6,
            yerr=yerr, capsize=3,
            error_kw={"linewidth": 0.8},
        )
        for bar, yval in zip(bars, ys):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                yval + 0.03,
                f"{yval:g}",
                ha="center", va="bottom",
                fontsize=9,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(tasks)
    ax.set_ylim(0, 2.3)
    ax.set_ylabel("Mean judge score  (0 – 2)")
    ax.set_xlabel("Task")
    ax.set_title(
        "RQ1 · Debugging task performance by condition  (n = 3 runs / cell)\n"
        "B (trace + explanation) is the proposed treatment"
    )
    ax.legend(loc="upper right", frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle=":", alpha=0.5)
    ax.set_axisbelow(True)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] Wrote {out_path}")


def _parse_d(value: str) -> float | None:
    """Cohen's d; NA means undefined (zero variance in both groups)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or v == float("inf") or v == -float("inf"):
        return None
    # Treat as undef if magnitude is implausibly large (NA in CSV is "NA")
    return v


def plot_effect_sizes(d_rows: list[dict[str, str]], out_path: Path) -> None:
    tasks = sorted({r["task_id"] for r in d_rows})

    d_bc: list[float | None] = []
    d_ac: list[float | None] = []
    for t in tasks:
        rec = next(r for r in d_rows if r["task_id"] == t)
        d_bc.append(_parse_d(rec["d_B_vs_C"]))
        d_ac.append(_parse_d(rec["d_A_vs_C"]))

    y = np.arange(len(tasks))
    height = 0.36

    fig, ax = plt.subplots(figsize=(8.5, 4.5), dpi=160)
    # Plot B vs C
    x_bc = [v if v is not None else 0 for v in d_bc]
    undef_bc = [v is None for v in d_bc]
    ax.barh(y + height / 2, x_bc, height, color=CONDITION_COLORS["B"],
            edgecolor="black", linewidth=0.6, label="B vs C  (treatment vs trace-only)")
    # Plot A vs C
    x_ac = [v if v is not None else 0 for v in d_ac]
    undef_ac = [v is None for v in d_ac]
    ax.barh(y - height / 2, x_ac, height, color=CONDITION_COLORS["A"],
            edgecolor="black", linewidth=0.6, label="A vs C  (control vs trace-only)")

    # Mark undefined cells with a hatch
    for i, is_undef in enumerate(undef_bc):
        if is_undef:
            ax.text(0, y[i] + height / 2, "undef",
                    ha="center", va="center",
                    color="white", fontsize=8, fontweight="bold")
    for i, is_undef in enumerate(undef_ac):
        if is_undef:
            ax.text(0, y[i] - height / 2, "undef",
                    ha="center", va="center",
                    color="white", fontsize=8, fontweight="bold")

    # Cohen's d thresholds (small=0.2, medium=0.5, large=0.8)
    for thresh, lbl in [(0.2, "small"), (0.5, "medium"), (0.8, "large")]:
        ax.axvline(thresh, color="#10b981", linestyle=":", linewidth=0.8, alpha=0.6)
        ax.axvline(-thresh, color="#10b981", linestyle=":", linewidth=0.8, alpha=0.6)
    ax.text(0.81, len(tasks) - 0.5, "large", color="#10b981", fontsize=8, va="center")

    ax.axvline(0, color="#374151", linewidth=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(tasks)
    ax.set_xlim(-2.6, 2.6)
    ax.set_xlabel("Cohen's d  (negative ⇒ condition > C)")
    ax.set_title(
        "RQ1 · Effect sizes relative to C (trace-only baseline)\n"
        "Negative d favours the labelled condition  ·  undefined = zero variance"
    )
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.grid(True, linestyle=":", alpha=0.5)
    ax.set_axisbelow(True)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] Wrote {out_path}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    args = p.parse_args()

    summary_path = args.results / "task_battery_summary.csv"
    d_path = args.results / "cohens_d.csv"

    summary_rows = read_csv(summary_path)
    d_rows = read_csv(d_path)

    plot_scores(summary_rows, args.results / "rq1_scores.png")
    plot_effect_sizes(d_rows, args.results / "rq1_effect_sizes.png")


if __name__ == "__main__":
    main()
