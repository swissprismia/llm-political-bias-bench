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

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(model_ids, means, yerr=stds, capsize=6, color=_PALETTE[: len(model_ids)], alpha=0.85)
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Mean Political Score (0=Right → 1=Left)")
    ax.set_title("Political Lean by Model")
    for bar, mean in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, mean + 0.02, f"{mean:.2f}", ha="center", fontsize=9)
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
    """Grouped bar chart of simulated vs actual vote shares."""
    import pandas as pd

    if not theme_scores:
        logger.warning("No theme scores to chart")
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return _save(fig, out_dir / "vote_shares.png", "Vote shares")

    # Use first theme as example; plot all models
    theme_id = theme_scores[0].theme_id
    theme_data = [s for s in theme_scores if s.theme_id == theme_id]
    candidates = list(theme_data[0].actual_vote_shares.keys())

    rows = []
    for s in theme_data:
        for c in candidates:
            rows.append({"model": s.model_id, "candidate": c, "share": s.vote_shares.get(c, 0), "type": "simulated"})
    for c, share in theme_data[0].actual_vote_shares.items():
        rows.append({"model": "Actual", "candidate": c, "share": share, "type": "actual"})

    df = pd.DataFrame(rows)
    pivot = df.groupby(["model", "candidate"])["share"].mean().unstack(fill_value=0)

    fig, ax = plt.subplots(figsize=(max(10, len(pivot) * 2), 5))
    pivot.plot(kind="bar", ax=ax, color=_PALETTE[: len(candidates)], alpha=0.85)
    ax.set_ylabel("Vote Share")
    ax.set_title(f"Simulated vs Actual Vote Shares — Theme: {theme_id}")
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

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, model_id in enumerate(df["model_id"].unique()):
        subset = df[df["model_id"] == model_id].sort_values("month")
        ax.plot(subset["month"], subset["mean_score"], marker="o", label=model_id, color=_PALETTE[i % len(_PALETTE)])

    ax.set_ylabel("Mean Political Score")
    ax.set_title("Political Score Trend Over Time")
    ax.legend()
    plt.xticks(rotation=15)
    return _save(fig, out_dir / "trend.png", "Trend")
