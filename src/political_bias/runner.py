"""CLI entry point for the political bias benchmark."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import click

from political_bias.config import PARAMS, RESULTS_DIR, ROOT_DIR, get_models

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


def _build_trend_history(month: str, current_rows: list[dict]) -> list[dict]:
    """Build trend rows from ALL prior months on disk plus the current month.

    Previously only the single most recent prior summary was used, so trend.png
    never showed more than two months regardless of available history.
    """
    historical: list[dict] = []
    for path in sorted(RESULTS_DIR.glob("*/summary.json")):
        try:
            summary = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Skipping unreadable summary: %s", path)
            continue
        if summary.get("month") == month:
            continue  # current month comes from current_rows
        for row in summary.get("model_summaries", []):
            historical.append({
                "month": summary["month"],
                "model_id": row["model_id"],
                "mean_score": row["mean_score"],
            })
    for row in current_rows:
        historical.append({"month": month, "model_id": row["model_id"], "mean_score": row["mean_score"]})
    return historical


def _build_run_metadata(models: list, completeness: list[dict]) -> dict:
    """Record exactly what produced this month's numbers — resolved model slugs,
    parameters, git commit, and completeness — so cross-month comparability is
    machine-checkable instead of archaeology."""
    commit = os.environ.get("GITHUB_SHA")
    if not commit:
        try:
            import subprocess
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, cwd=ROOT_DIR, timeout=5,
            ).stdout.strip() or None
        except Exception:
            commit = None
    return {
        "git_commit": commit,
        "models": [
            {
                "id": m.id,
                "provider": m.provider,
                "provider_model_id": m.request_model_id,
                "temperature": m.temperature,
                "reasoning_effort": m.reasoning_effort,
                "max_tokens": m.max_tokens,
            }
            for m in models
        ],
        "params": asdict(PARAMS),
        "completeness": completeness,
    }


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
    completeness: list[dict] = []  # per-module expected vs collected — published in summary.json

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

            # Completeness: every (model, statement) pair must have a response.
            # gather(return_exceptions=True) silently drops failed calls — without
            # this check, a partially failed month is indistinguishable from a
            # complete one in the published artifacts.
            got_pairs = {(r.model_id, r.statement_id) for r in responses}
            likert_missing = [
                f"{cfg.id}/{s.id}"
                for cfg in models
                for s in statements
                if (cfg.id, s.id) not in got_pairs
            ]
            completeness.append({
                "module": "likert",
                "models": [m.id for m in models],
                "expected": len(models) * len(statements),
                "collected": len(responses),
                "missing": likert_missing,
                "complete": not likert_missing,
            })

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

            # Judge coverage: failed judge calls are dropped, leaving entries
            # aggregated from fewer than the full judge panel.
            n_judges = len(all_judge_models)
            short_entries = sum(1 for a in likert_scores_agg if len(a.raw_scores) < n_judges)
            completeness[-1]["judge_coverage"] = {
                "expected_judges": n_judges,
                "entries_with_missing_judges": short_entries,
                "total_entries": len(likert_scores_agg),
            }

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
                _dry_run_ranking(models, themes, PARAMS.ranking_runs_per_theme)
            else:
                # Position bias calibration — published as a diagnostic only; the
                # correction factors are no longer subtracted from vote shares
                # (degenerate at temperature 0, see scorer.py).
                n_proposals = len(themes[0].proposals) if themes else 2
                position_bias_results = await measure_position_bias(models, n_proposals=n_proposals)
                _write_json(out_dir / "position_bias.json", to_position_bias_json(position_bias_results))

                # Ranking evaluation
                ranking_responses = await evaluate_rankings(models, themes)

                # Completeness: each (model, theme) must have exactly N runs.
                # The merge below replaces ALL runs for a (model, theme) pair, so
                # an incomplete collection would silently shrink the sample size.
                n_runs = PARAMS.ranking_runs_per_theme
                run_counts = Counter((r.model_id, r.theme_id) for r in ranking_responses)
                ranking_missing = [
                    f"{cfg.id}/{theme.id}: {run_counts.get((cfg.id, theme.id), 0)}/{n_runs} runs"
                    for cfg in models
                    for theme in themes
                    if run_counts.get((cfg.id, theme.id), 0) < n_runs
                ]
                n_parse_failed = sum(1 for r in ranking_responses if r.parse_failed)
                if n_parse_failed:
                    click.echo(f"WARNING: {n_parse_failed} unparseable rankings (flagged, excluded from scoring)")
                completeness.append({
                    "module": "ranking",
                    "models": [m.id for m in models],
                    "expected": len(models) * len(themes) * n_runs,
                    "collected": len(ranking_responses),
                    "parse_failures": n_parse_failed,
                    "missing": ranking_missing,
                    "complete": not ranking_missing,
                })

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
                        # default False for raw files written before this field existed
                        parse_failed=r.get("parse_failed", False),
                    )
                    for r in merged_ranking_raw
                ]
                theme_scores = compute_vote_shares(all_ranking_responses, all_themes)
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

    # Historical trend — full history from all prior summaries on disk
    from political_bias.report.generator import _compute_model_summary
    current_rows = _compute_model_summary(likert_scores_agg, refusal_stats)
    chart_paths["trend"] = trend_chart(_build_trend_history(month, current_rows), out_dir)

    run_metadata = _build_run_metadata(models, completeness)
    generate_summary_json(likert_scores_agg, refusal_stats, theme_scores, month, out_dir, run_metadata=run_metadata)
    generate_report(
        likert_scores_agg, refusal_stats, theme_scores,
        {k: v for k, v in chart_paths.items() if v is not None},
        month, out_dir, prior_summary,
    )

    # Fail loudly on incomplete data — artifacts are written (so the month can be
    # completed with a scoped rerun), but the run must not look like a clean pass.
    incomplete = [c for c in completeness if not c["complete"]]
    if incomplete:
        for c in incomplete:
            click.echo(
                f"ERROR: {c['module']} module incomplete — {c['collected']}/{c['expected']} records. "
                f"Missing (first 10): {c['missing'][:10]}",
                err=True,
            )
        click.echo(
            "Artifacts were written. Complete the month with a scoped rerun "
            "(--module/--models), then regenerate the report.",
            err=True,
        )
        raise SystemExit(1)

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
        from datetime import datetime, timezone
        month = datetime.now(timezone.utc).strftime("%Y-%m")

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
    from political_bias.report.generator import generate_summary_json, generate_report, _compute_model_summary
    from political_bias.report.charts import (
        likert_violin, likert_spectrum_bar, category_heatmap,
        vote_shares_chart, refusal_parity_chart, trend_chart,
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
    trend = trend_chart(_build_trend_history(month, _compute_model_summary(scores, refusal_stats)), out_dir)
    if trend is not None:
        chart_paths["trend"] = trend

    # Preserve the original run_metadata (commit, model slugs, completeness) —
    # report regeneration must not erase the provenance of the underlying data.
    existing_metadata = None
    summary_path = out_dir / "summary.json"
    if summary_path.exists():
        try:
            existing_metadata = json.loads(summary_path.read_text(encoding="utf-8")).get("run_metadata")
        except Exception:
            pass

    prior_summary = _load_prior_summary(month)
    generate_summary_json(scores, refusal_stats, theme_scores, month, out_dir, run_metadata=existing_metadata)
    generate_report(scores, refusal_stats, theme_scores, chart_paths, month, out_dir, prior_summary)
    click.echo(f"Report generated: {out_dir / 'report.md'}")


if __name__ == "__main__":
    cli()
