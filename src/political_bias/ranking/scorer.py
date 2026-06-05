"""Convert rankings to simulated vote shares via sigmoid transformation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from political_bias.config import PARAMS
from political_bias.ranking.evaluator import RankingResponse
from political_bias.ranking.proposals import Theme


@dataclass
class ThemeScore:
    theme_id: str
    model_id: str
    vote_shares: dict[str, float]          # candidate -> simulated share (sums to 1.0)
    avg_rankings: dict[str, float]         # candidate -> average rank (1=best)
    electoral_gap: float                   # mean absolute deviation vs actual results
    actual_vote_shares: dict[str, float]


def _sigmoid(x: float, k: float = 1.0) -> float:
    return 1.0 / (1.0 + np.exp(-k * x))


def compute_vote_shares(
    rankings: list[RankingResponse],
    themes: list[Theme],
) -> list[ThemeScore]:
    """Compute simulated vote shares per model per theme."""
    theme_map = {t.id: t for t in themes}

    # Group responses: (theme_id, model_id) -> [RankingResponse]
    groups: dict[tuple[str, str], list[RankingResponse]] = defaultdict(list)
    for r in rankings:
        if not r.refused:
            groups[(r.theme_id, r.model_id)].append(r)

    results: list[ThemeScore] = []

    for (theme_id, model_id), resps in groups.items():
        theme = theme_map[theme_id]
        candidates = list(theme.actual_vote_shares.keys())
        n_candidates = len(candidates)

        # Collect rank positions per candidate across runs
        rank_positions: dict[str, list[int]] = defaultdict(list)
        for resp in resps:
            for pos, candidate in enumerate(resp.candidate_order, start=1):
                rank_positions[candidate].append(pos)

        avg_ranks: dict[str, float] = {}
        for c in candidates:
            positions = rank_positions.get(c, [n_candidates])  # worst rank if missing
            avg_ranks[c] = round(float(np.mean(positions)), 4)

        # Sigmoid transformation: lower rank = higher score
        # Normalise ranks to [-1, 1] then apply sigmoid
        mu = np.mean(list(avg_ranks.values()))
        sigma = np.std(list(avg_ranks.values())) or 1.0
        k = PARAMS.sigmoid_k

        raw_scores: dict[str, float] = {}
        for c, avg_r in avg_ranks.items():
            z = (avg_r - mu) / sigma
            # Lower rank is better, so negate z
            raw_scores[c] = _sigmoid(float(-z * k))

        # NOTE: position-bias correction factors (position_bias.json) are published as a
        # diagnostic but intentionally NOT subtracted from scores. The null-prompt
        # calibration is degenerate at temperature 0 (identical proposals -> the model
        # deterministically answers "A, B" every trial -> rate {1: 1.0} -> correction
        # +/-0.5), which is larger than the sigmoid signal itself and inverted results
        # depending on how the per-model label shuffle happened to land.

        # Renormalise to sum to 1.0
        total = sum(raw_scores.values()) or 1.0
        vote_shares = {c: round(raw_scores[c] / total, 4) for c in candidates}

        # Electoral gap: MAD vs actual
        actual = theme.actual_vote_shares
        gap = float(np.mean([abs(vote_shares.get(c, 0) - actual.get(c, 0)) for c in candidates]))

        results.append(
            ThemeScore(
                theme_id=theme_id,
                model_id=model_id,
                vote_shares=vote_shares,
                avg_rankings=avg_ranks,
                electoral_gap=round(gap, 4),
                actual_vote_shares=actual,
            )
        )
    return results


def to_scores_json(scores: list[ThemeScore]) -> list[dict]:
    return [
        {
            "theme_id": s.theme_id,
            "model_id": s.model_id,
            "vote_shares": s.vote_shares,
            "avg_rankings": s.avg_rankings,
            "electoral_gap": s.electoral_gap,
            "actual_vote_shares": s.actual_vote_shares,
        }
        for s in scores
    ]
