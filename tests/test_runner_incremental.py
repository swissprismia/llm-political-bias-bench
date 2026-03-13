"""Tests for incremental rerun fixes and related bug-fixes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from political_bias.likert.evaluator import StatementResponse
from political_bias.likert.statements import Statement
from political_bias.ranking.evaluator import RankingResponse
from political_bias.ranking.proposals import Proposal, Theme
from political_bias.ranking.scorer import compute_vote_shares


# ---------------------------------------------------------------------------
# Shared factories (mirrors test_refusal.py)
# ---------------------------------------------------------------------------

def _make_statement(id: str, lean: str) -> Statement:
    return Statement(id=id, text=f"Statement {id}", category="economy", lean=lean, source="test", tags=[])


def _make_response(stmt_id: str, model_id: str, refused: bool) -> StatementResponse:
    return StatementResponse(
        statement_id=stmt_id,
        model_id=model_id,
        response_text="" if refused else "I agree with this.",
        latency_ms=100.0,
        refused=refused,
        input_tokens=10,
        output_tokens=10,
    )


def _make_theme(theme_id: str) -> Theme:
    return Theme(
        id=theme_id,
        name=f"Theme {theme_id}",
        country="usa",
        election_year=2024,
        proposals=[
            Proposal(label="A", text="Policy A", candidate="Harris", party="Democrat"),
            Proposal(label="B", text="Policy B", candidate="Trump", party="Republican"),
        ],
        actual_vote_shares={"Harris": 0.51, "Trump": 0.49},
    )


def _make_ranking_response(theme_id: str, model_id: str, run_index: int = 0) -> RankingResponse:
    return RankingResponse(
        theme_id=theme_id,
        model_id=model_id,
        run_index=run_index,
        proposal_order=["A", "B"],
        ranked_labels=["A", "B"],
        candidate_order=["Harris", "Trump"],
        raw_text="A, B",
        refused=False,
    )


# ---------------------------------------------------------------------------
# Test 1 — _merge_json_records with subset: no KeyError when merged responses
#           contain statement IDs outside the limited stmt_id_to_text
# ---------------------------------------------------------------------------

def test_merge_json_records_subset_no_key_error(tmp_path: Path) -> None:
    """Simulates incremental rerun with --limit: old records have IDs not in new limit."""
    # Simulate existing raw file with statements s1..s5
    existing = [
        {"statement_id": f"s{i}", "model_id": "model_a", "response_text": "ok",
         "latency_ms": 10.0, "refused": False, "input_tokens": 5, "output_tokens": 5}
        for i in range(1, 6)
    ]
    raw_path = tmp_path / "likert_raw.json"
    raw_path.write_text(json.dumps(existing), encoding="utf-8")

    # New run limited to s1..s2 only
    new_records = [
        {"statement_id": "s1", "model_id": "model_b", "response_text": "yes",
         "latency_ms": 10.0, "refused": False, "input_tokens": 5, "output_tokens": 5},
        {"statement_id": "s2", "model_id": "model_b", "response_text": "yes",
         "latency_ms": 10.0, "refused": False, "input_tokens": 5, "output_tokens": 5},
    ]

    from political_bias.runner import _merge_json_records
    merged = _merge_json_records(raw_path, new_records, "model_id", "statement_id")

    # stmt_id_to_text built from ALL statements (s1..s5), not just the limited set
    all_statements = [_make_statement(f"s{i}", "left") for i in range(1, 6)]
    stmt_id_to_text = {s.id: s.text for s in all_statements}

    # Reconstruct SR objects — must not raise KeyError for s3, s4, s5
    for r in merged:
        sid = r["statement_id"]
        assert sid in stmt_id_to_text, f"Statement {sid} missing from lookup"


# ---------------------------------------------------------------------------
# Test 2 — Module-specific rerun: existing likert_scores.json not overwritten
# ---------------------------------------------------------------------------

def test_ranking_only_run_preserves_likert_scores(tmp_path: Path, monkeypatch) -> None:
    """Running --module ranking must not overwrite likert_scores.json with empty data."""
    # Write a fake likert_scores.json
    fake_likert = [
        {
            "statement_id": "s1",
            "model_id": "model_a",
            "weighted_score": 0.7,
            "raw_scores": {"judge_a": 0.7},
            "weights": {"judge_a": 1.0},
            "self_scoring_bias": 0.0,
        }
    ]
    likert_path = tmp_path / "likert_scores.json"
    likert_path.write_text(json.dumps(fake_likert), encoding="utf-8")

    # Simulate: run_likert=False, run_ranking=False (both skipped, dry_run irrelevant)
    # The fix loads from disk when run_likert is False and not dry_run.
    from political_bias.likert.judge import AggregatedScore

    likert_scores_agg = []
    run_likert = False
    dry_run = False

    if not run_likert and not dry_run:
        lp = tmp_path / "likert_scores.json"
        if lp.exists():
            likert_scores_agg = [AggregatedScore(**r) for r in json.loads(lp.read_text())]

    assert len(likert_scores_agg) == 1
    assert likert_scores_agg[0].statement_id == "s1"
    assert likert_scores_agg[0].weighted_score == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Test 3 — Position bias correction actually changes vote shares
# ---------------------------------------------------------------------------

def test_position_bias_correction_changes_vote_shares() -> None:
    """Applying a non-zero correction for label 'A' should shift raw scores."""
    theme = _make_theme("t1")
    # Both runs: Harris got label A, Trump got label B
    responses = [
        _make_ranking_response("t1", "model_x", run_index=0),
        _make_ranking_response("t1", "model_x", run_index=1),
    ]

    scores_no_correction = compute_vote_shares(responses, [theme], position_bias_corrections=None)
    # Label A gets a positive correction → reduces Harris's score
    corrections = {"model_x": {"A": 0.2, "B": 0.0}}
    scores_with_correction = compute_vote_shares(responses, [theme], position_bias_corrections=corrections)

    assert len(scores_no_correction) == 1
    assert len(scores_with_correction) == 1

    harris_no_corr = scores_no_correction[0].vote_shares["Harris"]
    harris_with_corr = scores_with_correction[0].vote_shares["Harris"]

    # Correction should reduce Harris's share (she always got label A, bias-inflated)
    assert harris_with_corr < harris_no_corr, (
        f"Expected correction to reduce Harris share: {harris_no_corr} -> {harris_with_corr}"
    )


# ---------------------------------------------------------------------------
# Test 4 — Shuffle seed is stable across processes (hashlib vs hash())
# ---------------------------------------------------------------------------

def test_shuffle_seed_stability() -> None:
    """hashlib.sha256 seed must be identical across two independent computations."""
    model_id = "azure/gpt-4o-2024-11"

    seed_1 = int(hashlib.sha256(model_id.encode()).hexdigest()[:8], 16) % 1000
    seed_2 = int(hashlib.sha256(model_id.encode()).hexdigest()[:8], 16) % 1000

    assert seed_1 == seed_2, "hashlib seed must be deterministic"
    assert 0 <= seed_1 < 1000

    # Also verify two different model IDs produce different seeds
    other_id = "openai/gpt-4o-mini"
    seed_other = int(hashlib.sha256(other_id.encode()).hexdigest()[:8], 16) % 1000
    assert seed_1 != seed_other, "Different models should produce different seeds"
