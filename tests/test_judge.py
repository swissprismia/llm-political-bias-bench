"""Unit tests for multi-judge scoring and outlier weighting."""

import pytest

from political_bias.likert.judge import _compute_outlier_weights, aggregate_scores, JudgeScore


def test_outlier_weights_uniform():
    """When all scores are equal, all weights should be 1.0."""
    scores = [0.5, 0.5, 0.5, 0.5]
    weights = _compute_outlier_weights(scores)
    assert all(w == pytest.approx(1.0) for w in weights)


def test_outlier_weights_detects_outlier():
    """A clear outlier should receive reduced weight (0.5)."""
    scores = [0.5, 0.51, 0.49, 0.99]  # 0.99 is an outlier
    weights = _compute_outlier_weights(scores)
    # The outlier (0.99) should have reduced weight
    assert weights[3] < 1.0


def test_outlier_weights_few_scores():
    """With fewer than 3 scores, all weights should be 1.0."""
    weights = _compute_outlier_weights([0.2, 0.8])
    assert all(w == pytest.approx(1.0) for w in weights)


def test_aggregate_weighted_score_range():
    """Aggregated scores must be in [0, 1]."""
    judge_scores = [
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m1", score=0.3, reason=""),
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m2", score=0.4, reason=""),
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m3", score=0.5, reason=""),
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m4", score=0.6, reason=""),
    ]
    results = aggregate_scores(judge_scores, {})
    assert len(results) == 1
    assert 0.0 <= results[0].weighted_score <= 1.0


def test_self_scoring_bias_positive():
    """If self-score is higher than others, bias should be positive."""
    judge_scores = [
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m1", score=0.8, reason=""),  # self
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m2", score=0.4, reason=""),
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m3", score=0.4, reason=""),
    ]
    results = aggregate_scores(judge_scores, {})
    assert results[0].self_scoring_bias > 0


def test_self_judgment_excluded_from_weighted_score():
    """The self-judgment must carry weight 0.0 — the primary score aggregates peers only."""
    judge_scores = [
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m1", score=1.0, reason=""),  # self
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m2", score=0.4, reason=""),
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m3", score=0.4, reason=""),
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m4", score=0.4, reason=""),
    ]
    results = aggregate_scores(judge_scores, {})
    assert len(results) == 1
    # Peers all said 0.4 — the self score of 1.0 must not move the aggregate
    assert results[0].weighted_score == pytest.approx(0.4)
    # Full matrix retained, self published with explicit zero weight
    assert results[0].raw_scores["m1"] == pytest.approx(1.0)
    assert results[0].weights["m1"] == pytest.approx(0.0)
    # Diagnostic still computed: 1.0 vs peer average 0.4
    assert results[0].self_scoring_bias == pytest.approx(0.6)


def test_self_judgment_fallback_when_all_peers_failed():
    """If every peer judge failed, fall back to the self score rather than fabricating 0.5."""
    judge_scores = [
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="m1", score=0.7, reason=""),
    ]
    results = aggregate_scores(judge_scores, {})
    assert results[0].weighted_score == pytest.approx(0.7)
    assert results[0].weights["m1"] == pytest.approx(1.0)  # fallback is visible


def test_aggregate_groups_correctly():
    """Scores for different (statement, model) pairs should produce separate aggregations."""
    judge_scores = [
        JudgeScore(statement_id="s1", evaluated_model="m1", judge_model="j1", score=0.3, reason=""),
        JudgeScore(statement_id="s2", evaluated_model="m1", judge_model="j1", score=0.7, reason=""),
    ]
    results = aggregate_scores(judge_scores, {})
    assert len(results) == 2
    ids = {r.statement_id for r in results}
    assert ids == {"s1", "s2"}
