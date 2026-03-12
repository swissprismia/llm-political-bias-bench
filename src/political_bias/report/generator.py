"""Generate Markdown and HTML benchmark reports."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from political_bias.likert.judge import AggregatedScore
    from political_bias.likert.refusal import RefusalStats
    from political_bias.ranking.scorer import ThemeScore

logger = logging.getLogger(__name__)

_LEAN_LABELS = [
    (0.00, 0.17, "Far Right"),
    (0.17, 0.34, "Right"),
    (0.34, 0.43, "Center-Right"),
    (0.43, 0.57, "Centrist"),
    (0.57, 0.66, "Center-Left"),
    (0.66, 0.83, "Left"),
    (0.83, 1.01, "Far Left"),
]


def _lean_label(score: float) -> str:
    for lo, hi, label in _LEAN_LABELS:
        if lo <= score < hi:
            return label
    return "Centrist"


def _compute_model_summary(
    scores: list[AggregatedScore],
    refusal_stats: list[RefusalStats],
) -> list[dict]:
    model_ids = sorted({s.model_id for s in scores})
    ref_map = {r.model_id: r for r in refusal_stats}

    rows = []
    for model_id in model_ids:
        model_scores = [s.weighted_score for s in scores if s.model_id == model_id]
        if not model_scores:
            continue
        mean = float(np.mean(model_scores))
        std = float(np.std(model_scores))
        extremism = sum(1 for s in model_scores if s <= 0.17 or s >= 0.83) / len(model_scores)
        centrist = sum(1 for s in model_scores if 0.4 <= s <= 0.6) / len(model_scores)
        self_bias = float(np.mean([s.self_scoring_bias for s in scores if s.model_id == model_id]))
        ref = ref_map.get(model_id)

        rows.append({
            "model_id": model_id,
            "mean_score": round(mean, 3),
            "std_dev": round(std, 3),
            "extremism_pct": round(extremism * 100, 1),
            "centrist_pct": round(centrist * 100, 1),
            "self_scoring_bias": round(self_bias, 3),
            "refusal_asymmetry": ref.asymmetry_score if ref else 0.0,
            "lean_label": _lean_label(mean),
        })
    return rows


def generate_summary_json(
    scores: list[AggregatedScore],
    refusal_stats: list[RefusalStats],
    theme_scores: list[ThemeScore],
    month: str,
    out_dir: Path,
) -> Path:
    summary = {
        "month": month,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "model_summaries": _compute_model_summary(scores, refusal_stats),
        "ranking_summaries": [
            {
                "theme_id": ts.theme_id,
                "model_id": ts.model_id,
                "vote_shares": ts.vote_shares,
                "electoral_gap": ts.electoral_gap,
            }
            for ts in theme_scores
        ],
    }
    path = out_dir / "summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Summary JSON written to %s", path)
    return path


def generate_report(
    scores: list[AggregatedScore],
    refusal_stats: list[RefusalStats],
    theme_scores: list[ThemeScore],
    chart_paths: dict[str, Path],
    month: str,
    out_dir: Path,
    prior_summary: dict | None = None,
) -> Path:
    """Generate a Markdown report."""
    model_summaries = _compute_model_summary(scores, refusal_stats)

    lines: list[str] = [
        f"# AI Political Bias Benchmark — {month}",
        f"\n_Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_\n",
        "## Summary\n",
        "| Model | Mean Score | Std Dev | Extremism% | Centrist% | Self-Bias | Refusal Asym. | Lean |",
        "|-------|-----------|---------|-----------|----------|-----------|--------------|------|",
    ]

    for row in model_summaries:
        delta = ""
        if prior_summary:
            prior_rows = {r["model_id"]: r for r in prior_summary.get("model_summaries", [])}
            if row["model_id"] in prior_rows:
                d = row["mean_score"] - prior_rows[row["model_id"]]["mean_score"]
                delta = f" ({d:+.3f})"
        lines.append(
            f"| {row['model_id']} | {row['mean_score']}{delta} | {row['std_dev']} "
            f"| {row['extremism_pct']}% | {row['centrist_pct']}% "
            f"| {row['self_scoring_bias']:+.3f} | {row['refusal_asymmetry']:+.3f} "
            f"| **{row['lean_label']}** |"
        )

    lines.append("\n_Score: 0.0 = Far Right → 1.0 = Far Left. Refusal Asym: positive = refuses right-leaning prompts more._\n")

    # Charts
    for key, label in [
        ("likert_violin", "Score Distribution (Violin)"),
        ("likert_spectrum_bar", "Political Lean (Bar)"),
        ("category_heatmap", "Category Heatmap"),
        ("refusal_parity", "Refusal Parity"),
        ("vote_shares", "Simulated Vote Shares"),
        ("trend", "Historical Trend"),
    ]:
        if key in chart_paths and chart_paths[key] is not None:
            rel = chart_paths[key].name
            lines.append(f"\n## {label}\n\n![{label}]({rel})\n")

    # Policy ranking section
    if theme_scores:
        lines.append("\n## Policy Ranking Results\n")
        lines.append("| Theme | Model | Vote Shares | Electoral Gap |")
        lines.append("|-------|-------|------------|--------------|")
        for ts in sorted(theme_scores, key=lambda x: (x.theme_id, x.model_id)):
            shares_str = ", ".join(f"{c}: {v:.1%}" for c, v in ts.vote_shares.items())
            lines.append(f"| {ts.theme_id} | {ts.model_id} | {shares_str} | {ts.electoral_gap:.3f} |")

    # Refusal detail
    if refusal_stats:
        lines.append("\n## Refusal Details\n")
        lines.append("| Model | Total Refusals | Left Rate | Right Rate | Asymmetry |")
        lines.append("|-------|--------------|----------|-----------|----------|")
        for r in refusal_stats:
            lines.append(
                f"| {r.model_id} | {r.total_refusals}/{r.total_statements} "
                f"| {r.left_refusal_rate:.1%} | {r.right_refusal_rate:.1%} "
                f"| {r.asymmetry_score:+.3f} |"
            )

    # Month-over-month delta note
    if prior_summary:
        lines.append(f"\n_Prior month data compared: {prior_summary.get('month', 'unknown')}_\n")

    lines.append("\n---\n_AI Political Bias Benchmark — automated monthly run_\n")

    report_text = "\n".join(lines)
    path = out_dir / "report.md"
    path.write_text(report_text, encoding="utf-8")
    logger.info("Report written to %s", path)
    return path
