"""Generate charts for the benchmark report."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    from political_bias.likert.judge import AggregatedScore
    from political_bias.likert.refusal import RefusalStats
    from political_bias.ranking.scorer import ThemeScore

logger = logging.getLogger(__name__)

_PALETTE = ["#2196F3", "#F44336", "#4CAF50", "#FF9800", "#9C27B0", "#00BCD4"]


def _save(fig: plt.Figure, path: Path, title: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.debug("Saved chart: %s", path)
    return path


def likert_violin(
    scores: list[AggregatedScore],
    out_dir: Path,
) -> Path:
    """Violin plot of score distribution per model."""
    model_ids = sorted({s.model_id for s in scores})
    data_by_model = {m: [s.weighted_score for s in scores if s.model_id == m] for m in model_ids}

    fig, ax = plt.subplots(figsize=(10, 6))
    parts = ax.violinplot(
        [data_by_model[m] for m in model_ids],
        positions=range(len(model_ids)),
        showmedians=True,
    )
    for pc, color in zip(parts["bodies"], _PALETTE):  # type: ignore[call-overload]
        pc.set_facecolor(color)
        pc.set_alpha(0.7)

    ax.set_xticks(range(len(model_ids)))
    ax.set_xticklabels(model_ids, rotation=15, ha="right")
    ax.set_ylabel("Political Score (0=Right → 1=Left)")
    ax.set_title("Likert Score Distribution by Model")
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8, label="Centrist")
    ax.legend()
    return _save(fig, out_dir / "likert_violin.png", "Likert violin")


def likert_spectrum_bar(
    scores: list[AggregatedScore],
    out_dir: Path,
) -> Path:
    """Bar chart of mean score per model with std dev error bars."""
    model_ids = sorted({s.model_id for s in scores})
    means = [float(np.mean([s.weighted_score for s in scores if s.model_id == m])) for m in model_ids]
    stds = [float(np.std([s.weighted_score for s in scores if s.model_id == m])) for m in model_ids]

    # Refusals carry no score, so a model's count is the number of statements it answered.
    # Every model gets the same statements, so the largest count is the total asked.
    counts = [sum(1 for s in scores if s.model_id == m) for m in model_ids]
    total = max(counts)

    fig, ax = plt.subplots(figsize=(max(9, len(model_ids) * 1.6), 5))
    colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(model_ids))]
    bars = ax.bar(model_ids, means, yerr=stds, capsize=6, color=colors, alpha=0.85)
    for bar, n in zip(bars, counts):
        if n < total / 2:  # mean rests on few answers: fade it
            bar.set_alpha(0.3)
            bar.set_hatch("//")
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Mean Political Score (0=Right → 1=Left)")
    ax.set_title("Political Lean by Model (label: statements answered; faded = fewer than half)")
    for bar, mean, n in zip(bars, means, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, mean + 0.02, f"{mean:.2f}\n{n}/{total}", ha="center", fontsize=9)
    plt.xticks(rotation=15)
    return _save(fig, out_dir / "likert_spectrum_bar.png", "Likert spectrum bar")


def category_heatmap(
    scores: list[AggregatedScore],
    statements_by_id: dict[str, str],  # id -> category
    out_dir: Path,
) -> Path:
    """Heatmap of mean score per (model, category)."""
    import pandas as pd

    rows = []
    for s in scores:
        cat = statements_by_id.get(s.statement_id, "unknown")
        rows.append({"model": s.model_id, "category": cat, "score": s.weighted_score})

    df = pd.DataFrame(rows)
    pivot = df.groupby(["model", "category"])["score"].mean().unstack(fill_value=0.5)  # type: ignore[arg-type]

    fig, ax = plt.subplots(figsize=(max(8, len(pivot.columns) * 1.2), max(4, len(pivot) * 0.8)))
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdBu", vmin=0, vmax=1)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    plt.colorbar(im, ax=ax, label="Score (0=Right, 1=Left)")
    ax.set_title("Political Score Heatmap (Model × Category)")

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            ax.text(j, i, f"{pivot.values[i, j]:.2f}", ha="center", va="center", fontsize=7)

    return _save(fig, out_dir / "category_heatmap.png", "Category heatmap")


def vote_shares_chart(
    theme_scores: list[ThemeScore],
    out_dir: Path,
) -> Path:
    """Grouped bar chart of simulated vs actual vote shares, averaged across all themes."""
    import pandas as pd

    if not theme_scores:
        logger.warning("No theme scores to chart")
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return _save(fig, out_dir / "vote_shares.png", "Vote shares")

    rows = []
    for s in theme_scores:
        for c, share in s.vote_shares.items():
            rows.append({"model": s.model_id, "candidate": c, "share": share})
    # Actual shares once per theme (identical across models within a theme)
    actual_by_theme: dict[str, dict[str, float]] = {}
    for s in theme_scores:
        actual_by_theme.setdefault(s.theme_id, s.actual_vote_shares)
    for shares in actual_by_theme.values():
        for c, share in shares.items():
            rows.append({"model": "Actual", "candidate": c, "share": share})

    df = pd.DataFrame(rows)
    pivot = df.groupby(["model", "candidate"])["share"].mean().unstack(fill_value=0)
    n_candidates = len(pivot.columns)
    n_themes = len(actual_by_theme)

    fig, ax = plt.subplots(figsize=(max(10, len(pivot) * 2), 5))
    pivot.plot(kind="bar", ax=ax, color=_PALETTE[:n_candidates], alpha=0.85)
    ax.set_ylabel("Vote Share")
    ax.set_title(f"Simulated vs Actual Vote Shares — mean across {n_themes} themes")
    ax.legend(title="Candidate", bbox_to_anchor=(1, 1))
    plt.xticks(rotation=15, ha="right")
    return _save(fig, out_dir / "vote_shares.png", "Vote shares")


def refusal_parity_chart(
    refusal_stats: list[RefusalStats],
    out_dir: Path,
) -> Path:
    """Bar chart comparing left vs right refusal rates per model."""
    models = [s.model_id for s in refusal_stats]
    left_rates = [s.left_refusal_rate for s in refusal_stats]
    right_rates = [s.right_refusal_rate for s in refusal_stats]

    x = np.arange(len(models))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width / 2, left_rates, width, label="Left-leaning stmts", color="#2196F3", alpha=0.85)
    ax.bar(x + width / 2, right_rates, width, label="Right-leaning stmts", color="#F44336", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.set_ylabel("Refusal Rate")
    ax.set_title("Refusal Parity by Model")
    ax.legend()
    return _save(fig, out_dir / "refusal_parity.png", "Refusal parity")


def trend_chart(
    historical: list[dict],   # [{month, model_id, mean_score}]
    out_dir: Path,
) -> Path | None:
    """Monthly trend lines (requires ≥2 months of data)."""
    if len(historical) < 2:
        return None

    import pandas as pd

    df = pd.DataFrame(historical)
    if "month" not in df.columns:
        return None

    # One colour per vendor (model ids start with it: "gpt-…", "claude-…"), so successive
    # versions stay visually linked; each line is labelled with its model id at its last point.
    months = sorted(df["month"].unique())
    x_of = {m: i for i, m in enumerate(months)}
    vendors = list(dict.fromkeys(mid.split("-")[0] for mid in df["model_id"]))
    color_of = {v: _PALETTE[i % len(_PALETTE)] for i, v in enumerate(vendors)}

    fig, ax = plt.subplots(figsize=(12, 5.5))
    labels: dict[int, list[tuple[float, str, str]]] = {}
    for model_id in df["model_id"].unique():
        subset = df[df["model_id"] == model_id].sort_values("month")
        xs = [x_of[m] for m in subset["month"]]
        color = color_of[model_id.split("-")[0]]
        ax.plot(xs, subset["mean_score"], marker="o", color=color)
        labels.setdefault(xs[-1], []).append((float(subset["mean_score"].iloc[-1]), model_id, color))

    # Spread end labels that share an x position so they don't overlap.
    min_gap = 0.018
    for x, items in labels.items():
        prev = None
        for y, model_id, color in sorted(items):
            ly = y if prev is None else max(y, prev + min_gap)
            ax.annotate(model_id, (x, y), xytext=(x + 0.08, ly), textcoords="data",
                        va="center", fontsize=7, color=color)
            prev = ly

    for v, c in color_of.items():
        ax.plot([], [], color=c, marker="o", label=v)
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(months, rotation=15)
    ax.set_xlim(-0.5, len(months) - 0.5 + 1.2)  # room for end labels
    ax.set_ylabel("Mean Political Score")
    ax.set_title("Political Score Trend Over Time")
    ax.legend(title="Vendor", fontsize=8, loc="best")
    return _save(fig, out_dir / "trend.png", "Trend")
