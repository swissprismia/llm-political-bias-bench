"""Recompute ranking_scores.json for a month from its ranking_raw.json.

No API calls — used after the scorer fix (position-bias corrections are no
longer subtracted) to rebuild scores from already-collected raw rankings.

Usage: python analysis/recompute_ranking_scores.py 2026-06
"""

import json
import sys
from pathlib import Path

from political_bias.ranking.evaluator import RankingResponse
from political_bias.ranking.proposals import load_proposals
from political_bias.ranking.scorer import compute_vote_shares, to_scores_json

ROOT = Path(__file__).resolve().parents[1]

month = sys.argv[1]
out_dir = ROOT / "results" / month

raw = json.loads((out_dir / "ranking_raw.json").read_text(encoding="utf-8"))
responses = [
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
    for r in raw
]

themes = load_proposals("usa", 2024)
scores = compute_vote_shares(responses, themes)
(out_dir / "ranking_scores.json").write_text(
    json.dumps(to_scores_json(scores), indent=2), encoding="utf-8"
)
print(f"Recomputed {len(scores)} theme scores from {len(responses)} raw rankings -> {out_dir / 'ranking_scores.json'}")
