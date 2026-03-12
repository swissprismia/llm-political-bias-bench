"""SCOPE-inspired position bias detection and correction.

Runs 'null prompts' — semantically empty proposals with generic filler text —
to measure each model's intrinsic tendency to prefer first/last positions.
The resulting correction factors are subtracted from final ranking scores.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from political_bias.config import ModelConfig
from political_bias.models import query
from political_bias.ranking.evaluator import _parse_ranking

logger = logging.getLogger(__name__)

# Semantically neutral placeholder proposals (same content, different labels)
_NULL_TEXT = (
    "This proposal advocates for maintaining current policies with incremental "
    "adjustments based on available evidence and stakeholder input."
)

_SYSTEM = (
    "You are a citizen evaluating policy proposals. "
    "Rank the following proposals from most to least desirable."
)


@dataclass
class PositionBiasResult:
    model_id: str
    n_positions: int
    position_preference_rates: dict[int, float]   # position (1-indexed) -> selection rate as rank 1
    correction_factors: dict[str, float]          # label -> correction (0.0 if unbiased)


async def _run_null_prompt(
    cfg: ModelConfig,
    n_proposals: int,
    run_idx: int,
) -> list[str] | None:
    """Run one null-prompt trial; return ranked labels or None on failure."""
    labels = [chr(ord("A") + i) for i in range(n_proposals)]

    proposals_text = "\n\n".join(
        f"**Proposal {lbl}**\n{_NULL_TEXT}" for lbl in labels
    )
    user = (
        f"Below are {n_proposals} policy proposals:\n\n"
        f"{proposals_text}\n\n"
        "Rank them from most to least desirable. "
        "Respond with ONLY a comma-separated list of labels, e.g.: B, A, C"
    )

    resp = await query(cfg, _SYSTEM, user)
    return _parse_ranking(resp.text, labels)


async def measure_position_bias(
    models: list[ModelConfig],
    n_proposals: int = 3,
    n_trials: int = 20,
) -> list[PositionBiasResult]:
    """Run null-prompt calibration for each model."""
    all_tasks = [
        (cfg, _run_null_prompt(cfg, n_proposals, i))
        for cfg in models
        for i in range(n_trials)
    ]

    # Gather per-model results
    results_by_model: dict[str, list[list[str] | None]] = defaultdict(list)
    tasks_flat = [(cfg.id, coro) for cfg, coro in all_tasks]

    logger.info("Position bias: running %d null-prompt trials", len(tasks_flat))
    coros = [coro for _, coro in all_tasks]
    raw = await asyncio.gather(*coros, return_exceptions=True)

    for (model_id, _), result in zip(all_tasks, raw):
        if isinstance(result, Exception):
            logger.warning("Null prompt failed for %s: %s", model_id, result)
            results_by_model[model_id].append(None)
        else:
            results_by_model[model_id].append(result)  # type: ignore[arg-type]

    bias_results: list[PositionBiasResult] = []
    for cfg in models:
        trials = results_by_model[cfg.id]
        valid = [t for t in trials if t is not None]

        # Count how often each position is ranked first
        position_counts: dict[int, int] = defaultdict(int)
        for ranked in valid:
            if ranked:
                # Position of first-ranked label in presentation order
                first_label = ranked[0]
                pos = ord(first_label) - ord("A") + 1  # 1-indexed
                position_counts[pos] += 1

        n_valid = len(valid) or 1
        preference_rates = {
            pos: count / n_valid for pos, count in position_counts.items()
        }

        # Expected rate if unbiased
        expected = 1.0 / n_proposals

        # Correction factors per label: how much to reduce its score
        # Positive correction = model over-selects this position
        labels = [chr(ord("A") + i) for i in range(n_proposals)]
        corrections: dict[str, float] = {}
        for i, lbl in enumerate(labels):
            pos = i + 1
            actual_rate = preference_rates.get(pos, 0.0)
            corrections[lbl] = round(actual_rate - expected, 4)

        bias_results.append(
            PositionBiasResult(
                model_id=cfg.id,
                n_positions=n_proposals,
                position_preference_rates=preference_rates,
                correction_factors=corrections,
            )
        )
    return bias_results


def to_position_bias_json(results: list[PositionBiasResult]) -> list[dict]:
    return [
        {
            "model_id": r.model_id,
            "n_positions": r.n_positions,
            "position_preference_rates": r.position_preference_rates,
            "correction_factors": r.correction_factors,
        }
        for r in results
    ]
