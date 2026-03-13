"""CLI entry point for the political bias benchmark."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import click

from political_bias.config import RESULTS_DIR, get_models

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_out_dir(month: str) -> Path:
    out = RESULTS_DIR / month
    out.mkdir(parents=True, exist_ok=True)
    return out


def _load_prior_summary(month: str) -> dict | None:
    """Load summary from the most recent prior month's results."""
    year, mon = month.split("-")
    for delta in range(1, 13):
        m = int(mon) - delta
        y = int(year)
        while m < 1:
            m += 12
            y -= 1
        candidate = RESULTS_DIR / f"{y:04d}-{m:02d}" / "summary.json"
        if candidate.exists():
            return json.loads(candidate.read_text())
    return None


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("Wrote %s", path)


def _merge_json_records(
    path: Path,
    new_records: list[dict],
    model_key: str,
    record_key: str | None = None,
) -> list[dict]:
    """Load existing records, drop entries that overlap with new_records, then append.

    If record_key is given, only records matching both model_key and record_key are
    replaced — safe for partial (--limit) reruns. Without record_key, all records for
    the rerun models are dropped (correct for model-level data like refusal parity).
    """
    existing: list[dict] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if record_key:
        drop = {(r.get(model_key), r.get(record_key)) for r in new_records}
        kept = [r for r in existing if (r.get(model_key), r.get(record_key)) not in drop]
    else:
        drop_models = {r.get(model_key) for r in new_records}
        kept = [r for r in existing if r.get(model_key) not in drop_models]
    return kept + new_records


# ---------------------------------------------------------------------------
# Dry-run helpers
# ---------------------------------------------------------------------------

def _dry_run_likert(models, statements) -> None:
    click.echo(f"[dry-run] Likert: {len(models)} models × {len(statements)} statements")
    click.echo(f"[dry-run] Example prompt for statement '{statements[0].id}':")
    click.echo(f"  {statements[0].text[:80]}...")
    click.echo(f"[dry-run] Would generate {len(models) * len(statements)} LLM calls for responses.")
    click.echo(f"[dry-run] Would generate {len(models) * len(models) * len(statements)} LLM calls for judging.")


def _dry_run_ranking(models, themes, runs) -> None:
    click.echo(f"[dry-run] Ranking: {len(models)} models × {len(themes)} themes × {runs} runs = {len(models)*len(themes)*runs} calls")
    click.echo(f"[dry-run] SCOPE calibration: {len(models)} models × 20 null prompts = {len(models)*20} calls")


# ---------------------------------------------------------------------------
# Core benchmark coroutine
# ---------------------------------------------------------------------------

async def _run_benchmark(
    month: str,
    run_likert: bool,
    run_ranking: bool,
    model_names: list[str] | None,
    dry_run: bool,
    limit: int | None = None,
) -> None:
    from political_bias.likert.statements import load_statements, audit_balance
    from political_bias.likert.evaluator import evaluate_all, to_raw_json as likert_raw_json
    from political_bias.likert.judge import run_judging, to_scores_json as likert_scores_json
    from political_bias.likert.refusal import compute_refusal_parity, to_refusal_json
    from political_bias.ranking.proposals import load_proposals
    from political_bias.ranking.evaluator import evaluate_rankings, to_raw_json as ranking_raw_json
    from political_bias.ranking.scorer import compute_vote_shares, to_scores_json as ranking_scores_json
    from political_bias.ranking.position_bias import measure_position_bias, to_position_bias_json
    from political_bias.report.generator import generate_summary_json, generate_report
    from political_bias.report.charts import (
        likert_violin, likert_spectrum_bar, category_heatmap,
        vote_shares_chart, refusal_parity_chart, trend_chart,
    )

    models = get_models(model_names)
    out_dir = _resolve_out_dir(month)
    prior_summary = _load_prior_summary(month)

    click.echo(f"Benchmark month: {month}")
    click.echo(f"Models: {[m.id for m in models]}")
    click.echo(f"Output: {out_dir}")

    likert_scores_agg = []
    refusal_stats = []
    theme_scores = []
    position_bias_results = []

    # ------------------------------------------------------------------
    # Likert module
    # ------------------------------------------------------------------
    if run_likert:
        statements = load_statements()
        stmt_id_to_text = {s.id: s.text for s in statements}  # all IDs for lookup
        all_statements = statements  # keep full list for refusal parity
        if limit:
            statements = statements[:limit]  # only limit new evaluation calls
            click.echo(f"[smoke] Limiting to {limit} statements")
        balance = audit_balance(statements)
        click.echo(f"Loaded {len(statements)} statements. Balance: {balance['overall']}")

        if dry_run:
            _dry_run_likert(models, statements)
        else:
            # Evaluate new models
            responses = await evaluate_all(models, statements)

            # Merge with existing raw responses from other models
            merged_raw = _merge_json_records(
                out_dir / "likert_raw.json", likert_raw_json(responses), "model_id", "statement_id"
            )
            _write_json(out_dir / "likert_raw.json", merged_raw)

            # Reconstruct all StatementResponse objects for judging (new + existing)
            from political_bias.likert.evaluator import StatementResponse as SR
            all_responses = [
                SR(
                    statement_id=r["statement_id"],
                    model_id=r["model_id"],
                    response_text=r["response_text"],
                    latency_ms=r["latency_ms"],
                    refused=r["refused"],
                    input_tokens=r["input_tokens"],
                    output_tokens=r["output_tokens"],
                )
                for r in merged_raw
            ]

            # Judge using all currently configured models as judges
            all_judge_models = get_models()
            likert_scores_agg = await run_judging(all_judge_models, all_responses, stmt_id_to_text)
            _write_json(out_dir / "likert_scores.json", likert_scores_json(likert_scores_agg))

            # Refusal parity — compute from full merged responses so --limit reruns
            # don't replace a model's full-corpus stats with subset-only rates.
            refusal_stats = compute_refusal_parity(all_responses, all_statements)
            merged_refusal = _merge_json_records(
                out_dir / "refusal_parity.json", to_refusal_json(refusal_stats), "model_id"
            )
            _write_json(out_dir / "refusal_parity.json", merged_refusal)
            # Reload as RefusalStats for report generation
            from political_bias.likert.refusal import RefusalStats
            refusal_stats = [RefusalStats(**r) for r in merged_refusal]

    # ------------------------------------------------------------------
    # Ranking module
    # ------------------------------------------------------------------
    if run_ranking:
        try:
            all_themes = load_proposals("usa", 2024)
            themes = all_themes[:max(1, limit // 5)] if limit else all_themes
            click.echo(f"Loaded {len(themes)} themes for USA 2024")

            if dry_run:
                _dry_run_ranking(models, themes, 5)
            else:
                # Position bias calibration — match n_proposals to the actual theme data
                n_proposals = len(themes[0].proposals) if themes else 2
                position_bias_results = await measure_position_bias(models, n_proposals=n_proposals)
                _write_json(out_dir / "position_bias.json", to_position_bias_json(position_bias_results))

                corrections = {
                    r.model_id: r.correction_factors for r in position_bias_results
                }
                # Supplement with saved corrections for models not rerun in this invocation
                # so that compute_vote_shares applies calibration to all models in merged data.
                saved_pb_path = out_dir / "position_bias.json"
                if saved_pb_path.exists():
                    try:
                        for entry in json.loads(saved_pb_path.read_text(encoding="utf-8")):
                            if entry["model_id"] not in corrections:
                                corrections[entry["model_id"]] = entry["correction_factors"]
                    except Exception:
                        pass

                # Ranking evaluation
                ranking_responses = await evaluate_rankings(models, themes)
                merged_ranking_raw = _merge_json_records(
                    out_dir / "ranking_raw.json", ranking_raw_json(ranking_responses), "model_id", "theme_id"
                )
                _write_json(out_dir / "ranking_raw.json", merged_ranking_raw)

                # Recompute scores on merged data
                from political_bias.ranking.evaluator import RankingResponse
                all_ranking_responses = [
                    RankingResponse(
                        theme_id=r["theme_id"],
                        model_id=r["model_id"],
                        run_index=r["run_index"],
                        proposal_order=r["proposal_order"],
                        ranked_labels=r["ranked_labels"],
                        candidate_order=r["candidate_order"],
                        raw_text=r["raw_text"],
                        refused=r["refused"],
                    )
                    for r in merged_ranking_raw
                ]
                theme_scores = compute_vote_shares(all_ranking_responses, all_themes, corrections)
                _write_json(out_dir / "ranking_scores.json", ranking_scores_json(theme_scores))

        except FileNotFoundError:
            logger.warning("No USA 2024 proposals found — skipping ranking module")

    # Load saved data from disk for any module that was skipped, so the report
    # is not overwritten with empty data when running --module ranking or --module likert.
    if not run_likert and not dry_run:
        lp = out_dir / "likert_scores.json"
        rp = out_dir / "refusal_parity.json"
        if lp.exists():
            from political_bias.likert.judge import AggregatedScore
            likert_scores_agg = [AggregatedScore(**r) for r in json.loads(lp.read_text())]
        if rp.exists():
            from political_bias.likert.refusal import RefusalStats
            refusal_stats = [RefusalStats(**r) for r in json.loads(rp.read_text())]

    if not run_ranking and not dry_run:
        rsp = out_dir / "ranking_scores.json"
        if rsp.exists():
            from political_bias.ranking.scorer import ThemeScore
            theme_scores = [ThemeScore(**r) for r in json.loads(rsp.read_text())]

    if dry_run:
        click.echo("[dry-run] Dry run complete — no API calls made.")
        return

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------
    stmt_id_to_cat = {s.id: s.category for s in load_statements()}

    chart_paths: dict[str, Path | None] = {}
    if likert_scores_agg:
        chart_paths["likert_violin"] = likert_violin(likert_scores_agg, out_dir)
        chart_paths["likert_spectrum_bar"] = likert_spectrum_bar(likert_scores_agg, out_dir)
        chart_paths["category_heatmap"] = category_heatmap(likert_scores_agg, stmt_id_to_cat, out_dir)
    if refusal_stats:
        chart_paths["refusal_parity"] = refusal_parity_chart(refusal_stats, out_dir)
    if theme_scores:
        chart_paths["vote_shares"] = vote_shares_chart(theme_scores, out_dir)

    # Historical trend
    historical = []
    if prior_summary:
        for row in prior_summary.get("model_summaries", []):
            historical.append({"month": prior_summary["month"], "model_id": row["model_id"], "mean_score": row["mean_score"]})
    # Add current month
    from political_bias.report.generator import _compute_model_summary
    for row in _compute_model_summary(likert_scores_agg, refusal_stats):
        historical.append({"month": month, "model_id": row["model_id"], "mean_score": row["mean_score"]})
    chart_paths["trend"] = trend_chart(historical, out_dir)

    generate_summary_json(likert_scores_agg, refusal_stats, theme_scores, month, out_dir)
    generate_report(
        likert_scores_agg, refusal_stats, theme_scores,
        {k: v for k, v in chart_paths.items() if v is not None},
        month, out_dir, prior_summary,
    )

    click.echo(f"\nBenchmark complete. Results in: {out_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """AI Political Bias Benchmark CLI."""


@cli.command()
@click.option("--month", default=None, help="Month to run (YYYY-MM). Defaults to current month.")
@click.option("--module", type=click.Choice(["both", "likert", "ranking"]), default="both")
@click.option("--models", "model_list", default=None, help="Comma-separated model IDs.")
@click.option("--dry-run", is_flag=True, help="Validate setup without making API calls.")
@click.option("--limit", default=None, type=int, help="Limit number of statements/themes (smoke test).")
def run(month: str | None, module: str, model_list: str | None, dry_run: bool, limit: int | None) -> None:
    """Run the full benchmark (or a specific module)."""
    if month is None:
        from datetime import datetime
        month = datetime.utcnow().strftime("%Y-%m")

    model_names = [m.strip() for m in model_list.split(",")] if model_list else None

    asyncio.run(
        _run_benchmark(
            month=month,
            run_likert=module in ("both", "likert"),
            run_ranking=module in ("both", "ranking"),
            model_names=model_names,
            dry_run=dry_run,
            limit=limit,
        )
    )


@cli.command()
@click.option("--month", required=True, help="Month to generate report for (YYYY-MM).")
def report(month: str) -> None:
    """Generate a report from existing result data."""
    out_dir = _resolve_out_dir(month)

    likert_scores_path = out_dir / "likert_scores.json"
    refusal_path = out_dir / "refusal_parity.json"
    ranking_path = out_dir / "ranking_scores.json"

    if not likert_scores_path.exists():
        click.echo(f"No likert_scores.json found in {out_dir}", err=True)
        sys.exit(1)

    from political_bias.likert.judge import AggregatedScore
    from political_bias.likert.refusal import RefusalStats
    from political_bias.ranking.scorer import ThemeScore
    from political_bias.report.generator import generate_summary_json, generate_report
    from political_bias.report.charts import (
        likert_violin, likert_spectrum_bar, category_heatmap,
        vote_shares_chart, refusal_parity_chart,
    )
    from political_bias.likert.statements import load_statements

    raw_scores = json.loads(likert_scores_path.read_text())
    scores = [
        AggregatedScore(
            statement_id=r["statement_id"],
            model_id=r["model_id"],
            weighted_score=r["weighted_score"],
            raw_scores=r["raw_scores"],
            weights=r["weights"],
            self_scoring_bias=r["self_scoring_bias"],
        )
        for r in raw_scores
    ]

    refusal_stats = []
    if refusal_path.exists():
        raw_ref = json.loads(refusal_path.read_text())
        refusal_stats = [
            RefusalStats(**r) for r in raw_ref
        ]

    theme_scores = []
    if ranking_path.exists():
        raw_ranking = json.loads(ranking_path.read_text())
        theme_scores = [
            ThemeScore(
                theme_id=r["theme_id"],
                model_id=r["model_id"],
                vote_shares=r["vote_shares"],
                avg_rankings=r["avg_rankings"],
                electoral_gap=r["electoral_gap"],
                actual_vote_shares=r["actual_vote_shares"],
            )
            for r in raw_ranking
        ]

    stmts = load_statements()
    stmt_id_to_cat = {s.id: s.category for s in stmts}

    chart_paths: dict[str, Path] = {}
    chart_paths["likert_violin"] = likert_violin(scores, out_dir)
    chart_paths["likert_spectrum_bar"] = likert_spectrum_bar(scores, out_dir)
    chart_paths["category_heatmap"] = category_heatmap(scores, stmt_id_to_cat, out_dir)
    if refusal_stats:
        chart_paths["refusal_parity"] = refusal_parity_chart(refusal_stats, out_dir)
    if theme_scores:
        chart_paths["vote_shares"] = vote_shares_chart(theme_scores, out_dir)

    prior_summary = _load_prior_summary(month)
    generate_summary_json(scores, refusal_stats, theme_scores, month, out_dir)
    generate_report(scores, refusal_stats, theme_scores, chart_paths, month, out_dir, prior_summary)
    click.echo(f"Report generated: {out_dir / 'report.md'}")


if __name__ == "__main__":
    cli()
