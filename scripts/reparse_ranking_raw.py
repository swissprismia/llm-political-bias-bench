"""Re-parse historical ranking_raw.json with the fixed parser, then rescore.

No API calls. Months collected before the 2026-07 parser fix stored rankings
produced by a parser that uppercased the whole response (so the article "a"
matched label A) and fell back to presentation order — prose answers and soft
refusals were recorded as valid rankings. The raw_text is intact, so this
re-parses every response with the current parser, flags unparseable ones
(parse_failed=True, excluded from scoring), clears the presentation-order
fallback from refusals, and recomputes ranking_scores.json.

The label->candidate mapping is recovered from each record's own stored
ranking (the old fallback always stored a complete one) rather than from the
shuffle seed, which has changed scheme since these months were collected.

Usage: python scripts/reparse_ranking_raw.py 2026-03 [2026-04 ...]
"""

import json
import sys
from pathlib import Path

from political_bias.ranking.evaluator import RankingResponse, _parse_ranking, to_raw_json
from political_bias.ranking.proposals import load_proposals
from political_bias.ranking.scorer import compute_vote_shares, to_scores_json

ROOT = Path(__file__).resolve().parents[1]
themes = load_proposals("usa", 2024)

for month in sys.argv[1:]:
    out_dir = ROOT / "results" / month
    raw_path = out_dir / "ranking_raw.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))

    n_reordered = n_now_failed = n_refusals_cleared = 0
    responses: list[RankingResponse] = []
    for r in raw:
        expected = r["proposal_order"]
        mapping = dict(zip(r["ranked_labels"], r["candidate_order"]))

        if r["refused"]:
            # Refusals carry no ranking; the old code stored the presentation
            # order as a fallback, which the scorer must never see.
            if r["ranked_labels"]:
                n_refusals_cleared += 1
            ranked: list[str] = []
            cands: list[str] = []
            parse_failed = False
        else:
            parsed = _parse_ranking(r["raw_text"], expected)
            if parsed is None:
                if r["ranked_labels"]:
                    n_now_failed += 1
                ranked, cands, parse_failed = [], [], True
            else:
                if set(mapping) != set(expected):
                    raise SystemExit(
                        f"{month} {r['model_id']}/{r['theme_id']}#{r['run_index']}: "
                        f"cannot recover label->candidate mapping from stored record"
                    )
                if parsed != r["ranked_labels"]:
                    n_reordered += 1
                ranked, cands, parse_failed = parsed, [mapping[lbl] for lbl in parsed], False

        responses.append(
            RankingResponse(
                theme_id=r["theme_id"],
                model_id=r["model_id"],
                run_index=r["run_index"],
                proposal_order=expected,
                ranked_labels=ranked,
                candidate_order=cands,
                raw_text=r["raw_text"],
                refused=r["refused"],
                parse_failed=parse_failed,
            )
        )

    raw_path.write_text(json.dumps(to_raw_json(responses), indent=2), encoding="utf-8")
    scores = compute_vote_shares(responses, themes)
    (out_dir / "ranking_scores.json").write_text(
        json.dumps(to_scores_json(scores), indent=2), encoding="utf-8"
    )
    print(
        f"{month}: {len(responses)} records — {n_now_failed} reflagged as parse_failed, "
        f"{n_reordered} reordered by re-parse, {n_refusals_cleared} refusal fallbacks cleared "
        f"-> {len(scores)} theme scores"
    )
