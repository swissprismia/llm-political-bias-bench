"""Re-aggregate likert_scores.json for past months under the peer-only rule.

No API calls — the full judge matrix (raw_scores, self-judgment included) has
always been collected and published, so the 2026-07 aggregation change
(self-judgments carry weight 0.0 in the primary score) can be applied
retroactively to any month from the stored matrix. raw_scores and
self_scoring_bias are unchanged; only weighted_score and weights move.

After running this, regenerate each month's report in chronological order:
    python -m political_bias report --month YYYY-MM

Usage: python scripts/reaggregate_likert_scores.py 2026-03 [2026-04 ...]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from political_bias.likert.judge import JudgeScore, aggregate_scores, to_scores_json

ROOT = Path(__file__).resolve().parents[1]

for month in sys.argv[1:]:
    path = ROOT / "results" / month / "likert_scores.json"
    records = json.loads(path.read_text(encoding="utf-8"))

    # Rebuild the per-judge score list from the published matrix. Judge reasons
    # were never stored in likert_scores.json and are not needed to aggregate.
    judge_scores = [
        JudgeScore(
            statement_id=r["statement_id"],
            evaluated_model=r["model_id"],
            judge_model=judge_id,
            score=score,
            reason="",
        )
        for r in records
        for judge_id, score in r["raw_scores"].items()
    ]
    aggregated = aggregate_scores(judge_scores, {})

    # Per-model delta of the mean score, old aggregation vs peer-only.
    old_by_model: dict[str, list[float]] = defaultdict(list)
    new_by_model: dict[str, list[float]] = defaultdict(list)
    for r in records:
        old_by_model[r["model_id"]].append(r["weighted_score"])
    for a in aggregated:
        new_by_model[a.model_id].append(a.weighted_score)

    path.write_text(json.dumps(to_scores_json(aggregated), indent=2), encoding="utf-8")
    print(f"{month}: re-aggregated {len(aggregated)} entries -> {path}")
    for model_id in sorted(old_by_model):
        old_mean = sum(old_by_model[model_id]) / len(old_by_model[model_id])
        new_mean = sum(new_by_model[model_id]) / len(new_by_model[model_id])
        print(f"  {model_id}: mean {old_mean:.4f} -> {new_mean:.4f} (delta {new_mean - old_mean:+.4f})")
